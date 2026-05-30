from __future__ import annotations

from dataclasses import dataclass
import os

import pandas as pd

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover - depends on local OpenMP runtime availability.
    XGBRegressor = None


ML_FEATURE_COLUMNS = [
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
]

CATEGORICAL_FEATURES = [
    "category",
    "material_grade",
    "surface_finish",
    "supplier_region",
]


@dataclass(frozen=True)
class AiModelResult:
    priced_parts: pd.DataFrame
    model_metrics: pd.DataFrame
    feature_importance: pd.DataFrame
    cluster_summary: pd.DataFrame


def _preprocessor(scale_numeric: bool = False, extra_numeric: list[str] | None = None) -> ColumnTransformer:
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
    r2 = r2_score(actual, predicted) if len(actual) > 1 else 1.0
    return {
        "algorithm": name,
        "training_mae": mean_absolute_error(actual, predicted),
        "training_r2": r2,
    }


def _encoded_feature_names(pipeline: Pipeline) -> list[str]:
    preprocessor = pipeline.named_steps["preprocess"]
    return preprocessor.get_feature_names_out().tolist()


def _tree_feature_importance(pipeline: Pipeline, model_step: str, algorithm: str) -> pd.DataFrame:
    model = pipeline.named_steps[model_step]
    return pd.DataFrame(
        {
            "algorithm": algorithm,
            "feature": _encoded_feature_names(pipeline),
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)


def run_ai_pricing_models(parts: pd.DataFrame, max_clusters: int = 3) -> AiModelResult:
    """Apply thesis AI algorithms to priced part data.

    Supervised models learn the explainable should-cost output as the fair-price target.
    Isolation Forest flags unusual part/price patterns, and K-Means segments similar parts.
    """
    if "should_cost" not in parts.columns:
        raise ValueError("run_ai_pricing_models requires parts with a should_cost column.")

    result = parts.copy()
    X = result[ML_FEATURE_COLUMNS].copy()
    y = pd.to_numeric(result["should_cost"], errors="coerce")

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
        model.fit(X, y)
        result[prediction_column] = model.predict(X).clip(min=0)
        metrics = _model_metrics(algorithm, y, result[prediction_column])
        metrics["backend"] = xgboost_backend if algorithm == "XGBoost" else algorithm
        metric_rows.append(metrics)

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

    feature_importance = pd.concat(
        [
            _tree_feature_importance(random_forest_model, "model", "Random Forest"),
            _tree_feature_importance(xgboost_model, "model", "XGBoost"),
        ],
        ignore_index=True,
    )

    return AiModelResult(
        priced_parts=result,
        model_metrics=pd.DataFrame(metric_rows),
        feature_importance=feature_importance,
        cluster_summary=cluster_summary,
    )
