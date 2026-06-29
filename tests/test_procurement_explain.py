from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost
from dtp.ml_models import run_ai_pricing_models
from dtp.procurement_explain import build_procurement_explanations


def test_procurement_explanations_answer_review_questions() -> None:
    priced_parts = calculate_should_cost(pd.read_csv("data/sample_parts.csv").head(12))
    ai_parts = run_ai_pricing_models(priced_parts).priced_parts
    explanations = build_procurement_explanations(ai_parts)

    expected_columns = {
        "vendor",
        "erp_price",
        "fair_price",
        "top_price_increase_feature",
        "savings_opportunity",
        "erp_price_explanation",
        "negotiation_recommendation",
        "batna",
        "xai_summary",
    }
    assert expected_columns.issubset(explanations.columns)
    assert explanations["vendor"].notna().all()
    assert explanations["batna"].str.contains("BATNA").all()
    assert explanations["negotiation_recommendation"].str.len().min() > 20
