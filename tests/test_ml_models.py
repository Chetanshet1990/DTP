from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost
from dtp.ml_models import run_ai_pricing_models


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
    assert not result.cluster_summary.empty
    assert result.priced_parts["kmeans_cluster"].nunique() > 1


if __name__ == "__main__":
    test_all_requested_ai_algorithms_are_applied()
    print("ML model tests passed")
