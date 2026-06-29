from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost
from dtp.ml_models import prepare_ml_fair_price_pipeline, run_ai_pricing_models


def test_all_requested_ai_algorithms_are_applied() -> None:
    priced_parts = calculate_should_cost(pd.read_csv("data/sample_parts.csv"))
    result = run_ai_pricing_models(priced_parts)

    expected_prediction_columns = [
        "linear_regression_fair_price",
        "random_forest_fair_price",
        "xgboost_fair_price",
        "ai_predicted_fair_price",
        "isolation_forest_flag",
        "kmeans_cluster",
        "shap_top_feature",
        "shap_procurement_explanation",
    ]
    for column in expected_prediction_columns:
        assert column in result.priced_parts.columns

    assert set(result.model_metrics["algorithm"]) == {
        "Linear Regression",
        "Random Forest",
        "XGBoost",
    }
    assert set(result.feature_importance["algorithm"]) == {
        "Random Forest",
        "XGBoost",
    }
    assert not result.shap_explanations.empty
    assert result.shap_explanations["explanation_method"].notna().all()
    assert result.priced_parts["shap_procurement_explanation"].notna().all()
    assert not result.cluster_summary.empty
    assert result.priced_parts["kmeans_cluster"].nunique() > 1


def test_ml_pipeline_creates_cleaned_fair_price_labels_and_confidence() -> None:
    priced_parts = calculate_should_cost(pd.read_csv("data/sample_parts.csv"))
    pipeline_data = prepare_ml_fair_price_pipeline(
        priced_parts,
        commodity_index=310.0,
        fx_rate=84.0,
        market_source_status="fallback",
    )

    assert "ml_fair_price_label" in pipeline_data.columns
    assert "training_sample_weight" in pipeline_data.columns
    assert "prediction_confidence" in pipeline_data.columns
    assert "commodity_index" in pipeline_data.columns
    assert "fx_rate" in pipeline_data.columns
    assert pipeline_data["ml_fair_price_label"].notna().all()
    assert pipeline_data["training_sample_weight"].between(0, 1).all()
    assert set(pipeline_data["prediction_readiness"]) == {"Ready"}
    assert pipeline_data["prediction_confidence"].isin(["High", "Medium", "Low"]).all()


if __name__ == "__main__":
    test_all_requested_ai_algorithms_are_applied()
    test_ml_pipeline_creates_cleaned_fair_price_labels_and_confidence()
    print("ML model tests passed")
