from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost
from dtp.market_data import get_market_adjustment
from dtp.ml_models import run_ai_pricing_models
from dtp.procurement_explain import build_procurement_explanations


def _read_parts(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _save_chart(fig, output_path: Path) -> None:
    fig.update_layout(
        template="plotly_white",
        font={"family": "Arial", "size": 13},
        margin={"l": 45, "r": 30, "t": 70, "b": 45},
    )
    fig.write_html(output_path, include_plotlyjs="cdn")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(rows)


def _write_summary(
    output_dir: Path,
    ai_parts: pd.DataFrame,
    metrics: pd.DataFrame,
    label_quality: pd.DataFrame,
) -> None:
    anomaly_parts = int((ai_parts["isolation_forest_flag"] == "Anomaly").sum())
    cluster_count = int(ai_parts["kmeans_cluster"].nunique())
    explanation_coverage = ai_parts["shap_procurement_explanation"].notna().mean() * 100
    ready_parts = int((ai_parts["prediction_readiness"] == "Ready").sum())

    summary = pd.DataFrame(
        [
            {"result": "Parts evaluated", "value": len(ai_parts)},
            {"result": "Prediction-ready parts", "value": ready_parts},
            {"result": "Isolation Forest anomalies", "value": anomaly_parts},
            {"result": "K-Means clusters", "value": cluster_count},
            {"result": "SHAP explanation coverage percent", "value": explanation_coverage},
            {"result": "Best training R2", "value": metrics["training_r2"].max()},
            {"result": "Lowest training MAE", "value": metrics["training_mae"].min()},
            {"result": "Lowest training RMSE", "value": metrics["training_rmse"].min()},
        ]
    )
    summary.to_csv(output_dir / "prototype_ml_summary.csv", index=False)

    lines = [
        "# Prototype ML Results Summary",
        "",
        f"- Parts evaluated: {len(ai_parts)}",
        f"- Prediction-ready parts: {ready_parts}/{len(ai_parts)}",
        f"- Isolation Forest anomalies: {anomaly_parts}/{len(ai_parts)}",
        f"- K-Means clusters: {cluster_count}",
        f"- SHAP explanation coverage: {explanation_coverage:,.1f}%",
        f"- Best training R2: {metrics['training_r2'].max():,.3f}",
        f"- Lowest training MAE: INR {metrics['training_mae'].min():,.2f}",
        f"- Lowest training RMSE: INR {metrics['training_rmse'].min():,.2f}",
        "",
        "## Prediction Confidence",
        "",
        _markdown_table(label_quality),
    ]
    (output_dir / "prototype_ml_summary.md").write_text("\n".join(lines), encoding="utf-8")


def generate_ml_results(input_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    parts = _read_parts(input_path)
    market = get_market_adjustment()
    priced_parts = calculate_should_cost(
        parts,
        material_rate_factor=market.material_rate_factor,
    )
    result = run_ai_pricing_models(
        priced_parts,
        commodity_index=market.steel_index,
        fx_rate=market.usd_inr,
        market_source_status=market.source_status,
    )
    ai_parts = result.priced_parts

    ai_parts.to_csv(output_dir / "ml_priced_parts_results.csv", index=False)
    build_procurement_explanations(ai_parts).to_csv(
        output_dir / "ml_procurement_explanations.csv",
        index=False,
    )
    result.model_metrics.to_csv(output_dir / "ml_model_metrics.csv", index=False)
    result.feature_importance.to_csv(output_dir / "ml_feature_importance.csv", index=False)
    result.cluster_summary.to_csv(output_dir / "ml_cluster_summary.csv", index=False)
    result.shap_explanations.to_csv(output_dir / "ml_shap_explanations.csv", index=False)
    _write_summary(output_dir, ai_parts, result.model_metrics, result.label_quality)

    fit_fig = go.Figure()
    fit_fig.add_trace(
        go.Scatter(
            x=ai_parts["ml_fair_price_label"],
            y=ai_parts["linear_regression_fair_price"],
            mode="markers",
            name="Linear Regression",
        )
    )
    fit_fig.add_trace(
        go.Scatter(
            x=ai_parts["ml_fair_price_label"],
            y=ai_parts["random_forest_fair_price"],
            mode="markers",
            name="Random Forest",
        )
    )
    fit_fig.add_trace(
        go.Scatter(
            x=ai_parts["ml_fair_price_label"],
            y=ai_parts["xgboost_fair_price"],
            mode="markers",
            name="XGBoost",
        )
    )
    axis_min = min(ai_parts["ml_fair_price_label"].min(), ai_parts["ai_predicted_fair_price"].min())
    axis_max = max(ai_parts["ml_fair_price_label"].max(), ai_parts["ai_predicted_fair_price"].max())
    fit_fig.add_trace(
        go.Scatter(
            x=[axis_min, axis_max],
            y=[axis_min, axis_max],
            mode="lines",
            name="Ideal prediction",
            line={"dash": "dash", "color": "#555"},
        )
    )
    fit_fig.update_layout(
        title="Model Prediction Fit Against Cleaned Fair-Price Label",
        xaxis_title="Cleaned ML fair-price label, INR",
        yaxis_title="Model prediction, INR",
    )
    _save_chart(fit_fig, output_dir / "model_prediction_fit.html")

    residual_view = ai_parts.copy()
    residual_view["prediction_residual"] = (
        residual_view["ml_fair_price_label"] - residual_view["ai_predicted_fair_price"]
    )
    _save_chart(
        px.scatter(
            residual_view,
            x="ai_predicted_fair_price",
            y="prediction_residual",
            color="prediction_confidence",
            title="Residual Analysis for Ensemble ML Fair Price",
            labels={
                "ai_predicted_fair_price": "ML predicted fair price, INR",
                "prediction_residual": "Label minus prediction, INR",
                "prediction_confidence": "Prediction confidence",
            },
            hover_name="part_name",
            hover_data=["part_id", "category", "label_quality_status"],
        ),
        output_dir / "prediction_residuals.html",
    )

    _save_chart(
        px.scatter(
            ai_parts,
            x="ai_predicted_fair_price",
            y="should_cost",
            color="prediction_confidence",
            title="ML Predicted Fair Price vs Engineering Should-Cost",
            labels={
                "ai_predicted_fair_price": "ML predicted fair price, INR",
                "should_cost": "Engineering should-cost, INR",
            },
            hover_name="part_name",
            hover_data=["part_id", "category", "supplier_region", "shap_top_feature"],
        ),
        output_dir / "ml_fair_price_vs_should_cost.html",
    )

    _save_chart(
        px.bar(
            result.model_metrics,
            x="algorithm",
            y="training_mae",
            color="algorithm",
            title="Model Training MAE Comparison",
            labels={"algorithm": "Algorithm", "training_mae": "MAE, INR"},
        ),
        output_dir / "model_mae_comparison.html",
    )

    top_features = result.feature_importance.nlargest(20, "importance")
    _save_chart(
        px.bar(
            top_features,
            x="importance",
            y="feature",
            color="algorithm",
            orientation="h",
            title="Top ML Feature Importance Drivers",
            labels={"importance": "Importance", "feature": "Feature"},
        ),
        output_dir / "feature_importance.html",
    )

    _save_chart(
        px.scatter(
            ai_parts,
            x="weight_kg",
            y="ai_predicted_fair_price",
            color="kmeans_cluster",
            symbol="isolation_forest_flag",
            title="Part Segmentation and Anomaly Detection",
            labels={
                "weight_kg": "Weight, kg",
                "ai_predicted_fair_price": "ML predicted fair price, INR",
                "kmeans_cluster": "Cluster",
                "isolation_forest_flag": "Anomaly flag",
            },
            hover_name="part_name",
            hover_data=["part_id", "category", "material_grade", "shap_top_feature"],
        ),
        output_dir / "segmentation_anomaly_results.html",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate ML result tables and Plotly graphs for the DTP thesis demo.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "sample_parts.csv",
        help="Input part dataset CSV/XLSX.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "ml_results",
        help="Directory where result tables and graphs will be written.",
    )
    args = parser.parse_args()

    generate_ml_results(args.input, args.output_dir)
    print(f"ML result tables and graphs written to {args.output_dir}")


if __name__ == "__main__":
    main()
