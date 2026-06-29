from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

# This file is the AI layer. It prepares a clean fair-price label, trains
# supervised pricing models, detects anomalous parts, clusters similar parts,
# and produces SHAP/model explanations for the dashboard.

from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import shap
except Exception:  # pragma: no cover - optional thesis-grade explainability dependency.
    shap = None

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover - depends on local OpenMP runtime availability.
    XGBRegressor = None


ML_FEATURE_COLUMNS = [
    # These are the model inputs: drawing/OCR attributes, supplier region, volume,
    # and live market context. This is the answer to "what are your ML features?"
    "category",
    "material_grade",
    "thickness_mm",
    "length_mm",
    "width_mm",
    "weight_kg",
    "bend_count",
    "hole_count",
    "surface_finish",
    "material_rate_per_kg",
    "energy_kwh_per_part",
    "labour_hours",
    "supplier_region",
    "annual_volume",
    "commodity_index",
    "fx_rate",
]

NUMERIC_FEATURES = [
    "thickness_mm",
    "length_mm",
    "width_mm",
    "weight_kg",
    "bend_count",
    "hole_count",
    "material_rate_per_kg",
    "energy_kwh_per_part",
    "labour_hours",
    "annual_volume",
    "commodity_index",
    "fx_rate",
]

CATEGORICAL_FEATURES = [
    "category",
    "material_grade",
    "surface_finish",
    "supplier_region",
]

CRITICAL_OCR_AND_CONTEXT_FIELDS = [
    # If these fields are missing, prediction is blocked because the estimate would
    # not be commercially defensible.
    "material_grade",
    "weight_kg",
    "thickness_mm",
    "category",
    "supplier_region",
    "commodity_index",
    "fx_rate",
]

OPTIONAL_OCR_FIELDS = [
    # These can be imputed or tolerated with lower confidence in a future OCR flow.
    "length_mm",
    "width_mm",
    "bend_count",
    "hole_count",
    "surface_finish",
]

FAIR_LABEL_UPPER_GAP_PCT = 15.0
FAIR_LABEL_LOWER_GAP_PCT = -20.0


@dataclass(frozen=True)
class AiModelResult:
    """All AI outputs returned to the Streamlit dashboard."""
    priced_parts: pd.DataFrame
    model_metrics: pd.DataFrame
    feature_importance: pd.DataFrame
    cluster_summary: pd.DataFrame
    label_quality: pd.DataFrame
    shap_explanations: pd.DataFrame


def _preprocessor(scale_numeric: bool = False, extra_numeric: list[str] | None = None) -> ColumnTransformer:
    """Encode categorical features and optionally scale numeric features."""
    numeric_features = NUMERIC_FEATURES + (extra_numeric or [])
    numeric_step = StandardScaler() if scale_numeric else "passthrough"
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_step, numeric_features),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def _model_metrics(name: str, actual: pd.Series, predicted: pd.Series) -> dict[str, float | str]:
    """Calculate regression metrics shown in the AI Models tab."""
    r2 = r2_score(actual, predicted) if len(actual) > 1 else 1.0
    non_zero_actual = actual.replace(0, pd.NA).dropna()
    if non_zero_actual.empty:
        mape = 0.0
    else:
        aligned_predicted = predicted.loc[non_zero_actual.index]
        mape = ((non_zero_actual - aligned_predicted).abs() / non_zero_actual).mean() * 100
    return {
        "algorithm": name,
        "training_mae": mean_absolute_error(actual, predicted),
        "training_mape": float(mape),
        "training_rmse": mean_squared_error(actual, predicted) ** 0.5,
        "training_r2": r2,
    }


def _display_feature_name(encoded_name: str) -> str:
    """Convert encoded model feature names into dashboard labels."""
    if "__" in encoded_name:
        encoded_name = encoded_name.split("__", 1)[1]

    tokens = encoded_name.split("_")
    return "_".join(token[:1].upper() + token[1:] for token in tokens if token)


def _encoded_feature_names(pipeline: Pipeline) -> list[str]:
    """Get readable feature names after one-hot encoding."""
    preprocessor = pipeline.named_steps["preprocess"]
    return [
        _display_feature_name(feature_name)
        for feature_name in preprocessor.get_feature_names_out().tolist()
    ]


def _tree_feature_importance(pipeline: Pipeline, model_step: str, algorithm: str) -> pd.DataFrame:
    """Extract global feature importance from tree-based models."""
    model = pipeline.named_steps[model_step]
    return pd.DataFrame(
        {
            "algorithm": algorithm,
            "feature": _encoded_feature_names(pipeline),
            "importance": model.feature_importances_,
            "explanation_method": "Tree feature importance",
        }
    ).sort_values("importance", ascending=False)


def _shap_or_importance_explanations(
    pipeline: Pipeline,
    X: pd.DataFrame,
    part_ids: pd.Series,
    algorithm: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return global and part-level explanations.

    True SHAP is used when the optional shap package is installed. In lean demo
    environments the function falls back to tree feature importance so the app
    still exposes a stable procurement explanation surface.
    """
    feature_names = _encoded_feature_names(pipeline)
    preprocessor = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    encoded_X = preprocessor.transform(X)

    if shap is not None:
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(encoded_X)
            if isinstance(shap_values, list):
                shap_values = shap_values[0]
            shap_values = np.asarray(shap_values, dtype=float)
            global_explanation = pd.DataFrame(
                {
                    "algorithm": algorithm,
                    "feature": feature_names,
                    "importance": np.abs(shap_values).mean(axis=0),
                    "explanation_method": "SHAP TreeExplainer mean absolute value",
                }
            ).sort_values("importance", ascending=False)

            part_rows = []
            for row_index, part_id in enumerate(part_ids):
                row_values = shap_values[row_index]
                top_index = int(np.argmax(np.abs(row_values)))
                direction = "increases" if row_values[top_index] >= 0 else "decreases"
                part_rows.append(
                    {
                        "part_id": part_id,
                        "algorithm": algorithm,
                        "top_feature": feature_names[top_index],
                        "top_feature_impact": row_values[top_index],
                        "explanation_method": "SHAP TreeExplainer",
                        "procurement_explanation": (
                            f"{feature_names[top_index]} {direction} the predicted fair price"
                        ),
                    }
                )
            return global_explanation, pd.DataFrame(part_rows)
        except Exception:
            pass

    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        importances = np.zeros(len(feature_names), dtype=float)
    importances = np.asarray(importances, dtype=float)
    global_explanation = pd.DataFrame(
        {
            "algorithm": algorithm,
            "feature": feature_names,
            "importance": importances,
            "explanation_method": "Tree feature importance fallback",
        }
    ).sort_values("importance", ascending=False)

    top_feature = (
        global_explanation.iloc[0]["feature"]
        if not global_explanation.empty
        else "No dominant feature"
    )
    part_explanation = pd.DataFrame(
        {
            "part_id": part_ids.to_list(),
            "algorithm": algorithm,
            "top_feature": top_feature,
            "top_feature_impact": float(global_explanation.iloc[0]["importance"])
            if not global_explanation.empty
            else 0.0,
            "explanation_method": "Tree feature importance fallback",
            "procurement_explanation": (
                f"{top_feature} is the strongest global driver in the current model"
            ),
        }
    )
    return global_explanation, part_explanation


def _missing_fields(row: pd.Series, fields: list[str]) -> list[str]:
    """Return fields missing in one part row."""
    missing = []
    for field in fields:
        value = row.get(field)
        if pd.isna(value) or str(value).strip() == "":
            missing.append(field)
    return missing


def _prediction_confidence(row: pd.Series, market_source_status: str) -> str:
    """Convert data quality, history, and market freshness into High/Medium/Low."""
    if row["prediction_readiness"] == "Blocked":
        return "Blocked"
    score = 3
    if row["similar_erp_history_count"] < 2:
        score -= 1
    if row["label_quality_status"] != "Clean ERP label":
        score -= 1
    if market_source_status != "live":
        score -= 1
    if row["optional_missing_fields"]:
        score -= 1
    if score >= 3:
        return "High"
    if score == 2:
        return "Medium"
    return "Low"


def prepare_ml_fair_price_pipeline(
    parts: pd.DataFrame,
    commodity_index: float = 1.0,
    fx_rate: float = 1.0,
    market_source_status: str = "live",
) -> pd.DataFrame:
    """Prepare executable V1 fair-price ML inputs and labels.

    The current repository has part-level demo data, so this function creates a
    cleaned fair-price label from available ERP/current price plus should-cost
    anchor. When real OCR and ERP joins arrive, this is the replacement point
    for transaction-level cleaning and time-based market normalization.
    """
    if "should_cost" not in parts.columns:
        raise ValueError("prepare_ml_fair_price_pipeline requires a should_cost column.")

    result = parts.copy()

    # Add current market context as model features. If live values are missing,
    # the caller passes baseline values and market_source_status="fallback".
    if "commodity_index" not in result.columns:
        result["commodity_index"] = commodity_index
    if "fx_rate" not in result.columns:
        result["fx_rate"] = fx_rate

    for column in NUMERIC_FEATURES + ["erp_price", "should_cost", "annual_volume"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    # Check whether the drawing/OCR/context inputs are good enough for ML.
    result["critical_missing_fields"] = result.apply(
        lambda row: ", ".join(_missing_fields(row, CRITICAL_OCR_AND_CONTEXT_FIELDS)),
        axis=1,
    )
    result["optional_missing_fields"] = result.apply(
        lambda row: ", ".join(_missing_fields(row, OPTIONAL_OCR_FIELDS)),
        axis=1,
    )
    result["prediction_readiness"] = result["critical_missing_fields"].apply(
        lambda value: "Blocked" if value else "Ready"
    )

    result["raw_erp_price_label"] = result["erp_price"]
    result["erp_to_should_cost_gap_pct"] = (
        (result["erp_price"] - result["should_cost"]) / result["should_cost"] * 100
    )
    result["ml_fair_price_label"] = result["erp_price"].astype(float)
    result["label_quality_status"] = "Clean ERP label"

    # IMPORTANT REVIEW POINT:
    # Raw ERP price is not used blindly as truth. If it is far above or below
    # should-cost, the label is clipped toward the should-cost anchor and given
    # lower training weight. This avoids teaching the model bad negotiation noise.
    high_gap = result["erp_to_should_cost_gap_pct"] > FAIR_LABEL_UPPER_GAP_PCT
    low_gap = result["erp_to_should_cost_gap_pct"] < FAIR_LABEL_LOWER_GAP_PCT
    missing_erp = result["erp_price"].isna() | (result["erp_price"] <= 0)
    blocked = result["prediction_readiness"] == "Blocked"

    result.loc[high_gap, "ml_fair_price_label"] = result.loc[high_gap, "should_cost"] * (
        1 + FAIR_LABEL_UPPER_GAP_PCT / 100
    )
    result.loc[high_gap, "label_quality_status"] = "ERP high outlier clipped to should-cost anchor"

    result.loc[low_gap, "ml_fair_price_label"] = result.loc[low_gap, "should_cost"] * (
        1 + FAIR_LABEL_LOWER_GAP_PCT / 100
    )
    result.loc[low_gap, "label_quality_status"] = "ERP low outlier lifted toward should-cost anchor"

    result.loc[missing_erp, "ml_fair_price_label"] = result.loc[missing_erp, "should_cost"]
    result.loc[missing_erp, "label_quality_status"] = "Missing ERP label; using should-cost anchor"

    result.loc[blocked, "ml_fair_price_label"] = result.loc[blocked, "should_cost"]
    result.loc[blocked, "label_quality_status"] = "Blocked critical fields; using should-cost anchor"

    result["training_sample_weight"] = 1.0
    result.loc[high_gap | low_gap, "training_sample_weight"] = 0.45
    result.loc[missing_erp | blocked, "training_sample_weight"] = 0.25

    similarity_keys = ["category", "material_grade", "supplier_region"]
    # Similar history count is a simple V1 confidence signal. More similar parts
    # means the ML estimate is more defensible.
    result["similar_erp_history_count"] = (
        result.groupby(similarity_keys)["part_id"].transform("count")
        if all(column in result.columns for column in similarity_keys + ["part_id"])
        else 0
    )
    result["prediction_confidence"] = result.apply(
        lambda row: _prediction_confidence(row, market_source_status),
        axis=1,
    )
    result["market_source_status"] = market_source_status

    return result


def _fit_model(model: Pipeline, X: pd.DataFrame, y: pd.Series, sample_weight: pd.Series) -> None:
    try:
        model.fit(X, y, model__sample_weight=sample_weight)
    except TypeError:
        model.fit(X, y)


def run_ai_pricing_models(
    parts: pd.DataFrame,
    max_clusters: int = 3,
    commodity_index: float = 1.0,
    fx_rate: float = 1.0,
    market_source_status: str = "live",
) -> AiModelResult:
    """Apply thesis AI algorithms to priced part data.

    Supervised models learn a cleaned ML fair-price label derived from ERP/current
    price, anomaly rules, market context, and should-cost anchor. Isolation Forest
    flags unusual part/price patterns, and K-Means segments similar parts.
    """
    if "should_cost" not in parts.columns:
        raise ValueError("run_ai_pricing_models requires parts with a should_cost column.")

    # 1) Prepare ML-ready features and target label.
    result = prepare_ml_fair_price_pipeline(
        parts,
        commodity_index=commodity_index,
        fx_rate=fx_rate,
        market_source_status=market_source_status,
    )
    X = result[ML_FEATURE_COLUMNS].copy()
    y = pd.to_numeric(result["ml_fair_price_label"], errors="coerce")
    sample_weight = pd.to_numeric(result["training_sample_weight"], errors="coerce").fillna(1.0)

    # 2) Build supervised fair-price models.
    # Linear Regression = academic baseline.
    # Random Forest = non-linear benchmark.
    # XGBoost = primary tabular model, with GradientBoosting fallback on systems
    # where native XGBoost dependencies are unavailable.
    linear_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor(scale_numeric=True)),
            ("model", LinearRegression()),
        ]
    )
    random_forest_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=200,
                    random_state=42,
                    min_samples_leaf=1,
                ),
            ),
        ]
    )
    if XGBRegressor is None:
        xgboost_backend = "GradientBoosting fallback; install libomp for native XGBoost on macOS"
        xgboost_estimator = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            random_state=42,
        )
    else:
        xgboost_backend = "XGBRegressor"
        xgboost_estimator = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
            n_jobs=1,
        )

    xgboost_model = Pipeline(
        steps=[
            ("preprocess", _preprocessor()),
            ("model", xgboost_estimator),
        ]
    )

    trained_models = [
        ("Linear Regression", "linear_regression_fair_price", linear_model),
        ("Random Forest", "random_forest_fair_price", random_forest_model),
        ("XGBoost", "xgboost_fair_price", xgboost_model),
    ]

    metric_rows = []
    for algorithm, prediction_column, model in trained_models:
        _fit_model(model, X, y, sample_weight)
        result[prediction_column] = model.predict(X).clip(min=0)
        metrics = _model_metrics(algorithm, y, result[prediction_column])
        metrics["backend"] = xgboost_backend if algorithm == "XGBoost" else algorithm
        metrics["target_label"] = "ml_fair_price_label"
        metric_rows.append(metrics)

    # 3) Ensemble output: average the three supervised model predictions.
    # This becomes the ML Predicted Fair Price shown in the dashboard.
    result["ai_predicted_fair_price"] = result[
        [
            "linear_regression_fair_price",
            "random_forest_fair_price",
            "xgboost_fair_price",
        ]
    ].mean(axis=1)
    result["ai_price_gap"] = result["erp_price"] - result["ai_predicted_fair_price"]
    result["ai_price_gap_pct"] = result["ai_price_gap"] / result["ai_predicted_fair_price"] * 100
    result["ai_savings_opportunity"] = result["ai_price_gap"].clip(lower=0) * result["annual_volume"]
    result["should_cost_variance"] = result["ai_predicted_fair_price"] - result["should_cost"]
    result["should_cost_variance_pct"] = result["should_cost_variance"] / result["should_cost"] * 100

    # 4) Isolation Forest flags unusual combinations of engineering features,
    # market context, ERP price, and price gap.
    anomaly_features = result[ML_FEATURE_COLUMNS + ["erp_price", "price_gap_pct"]].copy()
    anomaly_pipeline = Pipeline(
        steps=[
            ("preprocess", _preprocessor(scale_numeric=True, extra_numeric=["erp_price", "price_gap_pct"])),
            (
                "model",
                IsolationForest(
                    contamination="auto",
                    random_state=42,
                ),
            ),
        ]
    )
    anomaly_pipeline.fit(anomaly_features)
    anomaly_labels = anomaly_pipeline.predict(anomaly_features)
    result["isolation_forest_score"] = anomaly_pipeline.decision_function(anomaly_features)
    result["isolation_forest_flag"] = [
        "Anomaly" if label == -1 else "Normal"
        for label in anomaly_labels
    ]

    # 5) K-Means groups similar parts so procurement can benchmark clusters.
    cluster_count = min(max_clusters, len(result))
    cluster_pipeline = Pipeline(
        steps=[
            ("preprocess", _preprocessor(scale_numeric=True)),
            (
                "model",
                KMeans(
                    n_clusters=cluster_count,
                    random_state=42,
                    n_init=10,
                ),
            ),
        ]
    )
    result["kmeans_cluster"] = cluster_pipeline.fit_predict(X) + 1

    cluster_summary = (
        result.groupby("kmeans_cluster", as_index=False)
        .agg(
            parts=("part_id", "count"),
            avg_erp_price=("erp_price", "mean"),
            avg_ai_fair_price=("ai_predicted_fair_price", "mean"),
            avg_gap_pct=("ai_price_gap_pct", "mean"),
            qualified_savings=("ai_savings_opportunity", "sum"),
        )
        .sort_values("kmeans_cluster")
    )

    # 6) Explainability: feature importance plus SHAP part-level explanation.
    tree_feature_importance = pd.concat(
        [
            _tree_feature_importance(random_forest_model, "model", "Random Forest"),
            _tree_feature_importance(xgboost_model, "model", "XGBoost"),
        ],
        ignore_index=True,
    )
    shap_global, shap_parts = _shap_or_importance_explanations(
        xgboost_model,
        X,
        result["part_id"],
        "XGBoost",
    )
    feature_importance = pd.concat(
        [tree_feature_importance, shap_global],
        ignore_index=True,
    )
    result = result.merge(
        shap_parts[
            [
                "part_id",
                "top_feature",
                "top_feature_impact",
                "explanation_method",
                "procurement_explanation",
            ]
        ].rename(
            columns={
                "top_feature": "shap_top_feature",
                "top_feature_impact": "shap_top_feature_impact",
                "explanation_method": "shap_explanation_method",
                "procurement_explanation": "shap_procurement_explanation",
            }
        ),
        on="part_id",
        how="left",
    )

    return AiModelResult(
        priced_parts=result,
        model_metrics=pd.DataFrame(metric_rows),
        feature_importance=feature_importance,
        cluster_summary=cluster_summary,
        label_quality=(
            result.groupby(["label_quality_status", "prediction_confidence"], as_index=False)
            .agg(parts=("part_id", "count"), avg_sample_weight=("training_sample_weight", "mean"))
            .sort_values(["label_quality_status", "prediction_confidence"])
        ),
        shap_explanations=shap_parts,
    )
