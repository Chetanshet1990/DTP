from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost
from dtp.drawing_extractor import SPEC_FIELDS, extract_specs_from_text
from dtp.ml_models import run_ai_pricing_models


def _missing_specs(parts: pd.DataFrame) -> pd.Series:
    return parts[SPEC_FIELDS].apply(
        lambda row: sum(pd.isna(value) or str(value).strip() == "" for value in row),
        axis=1,
    )


def test_sm1001_commit_makes_row_ready_and_reruns_ml_pipeline() -> None:
    active_parts = pd.read_csv(PROJECT_ROOT / "data/sample_parts.csv")
    sm1001_mask = active_parts["part_id"].eq("SM-1001")
    assert sm1001_mask.sum() == 1
    active_parts.loc[sm1001_mask, SPEC_FIELDS] = pd.NA
    active_parts.loc[sm1001_mask, "engineering_status"] = "Awaiting drawing"
    active_parts.loc[sm1001_mask, "prediction_status"] = "Blocked"
    assert active_parts.loc[sm1001_mask, "engineering_status"].iloc[0] == "Awaiting drawing"
    assert active_parts.loc[sm1001_mask, "prediction_status"].iloc[0] == "Blocked"
    assert int(_missing_specs(active_parts).loc[sm1001_mask].iloc[0]) == len(SPEC_FIELDS)

    extracted = extract_specs_from_text(
        """
        Category: Bracket
        Material: Mild Steel
        Material Grade: IS 2062 E250
        Thickness: 4.0 mm
        Length: 401 mm
        Width: 330 mm
        Weight: 3.42 kg
        Bend Count: 2
        Hole Count: 16
        Surface Finish: Painted
        """
    )
    candidate = active_parts.copy()
    for field, value in extracted.extracted_specs.items():
        candidate.loc[sm1001_mask, field] = value

    ready_parts = candidate.loc[_missing_specs(candidate).eq(0)].copy()
    assert len(ready_parts) == 120

    priced = calculate_should_cost(ready_parts)
    ml_result = run_ai_pricing_models(priced)
    committed_row = ml_result.priced_parts.loc[
        ml_result.priced_parts["part_id"].eq("SM-1001")
    ].iloc[0]
    assert committed_row["bend_count"] == 2
    assert committed_row["hole_count"] == 16
    assert committed_row["ai_predicted_fair_price"] > 0
    assert pd.notna(committed_row["shap_procurement_explanation"])


if __name__ == "__main__":
    test_sm1001_commit_makes_row_ready_and_reruns_ml_pipeline()
    print("Drawing ingestion pipeline tests passed")
