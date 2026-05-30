from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.cost_model import calculate_should_cost


def _base_part(erp_price: float) -> dict[str, object]:
    return {
        "part_id": "SM-TEST",
        "part_name": "Test bracket",
        "category": "Bracket",
        "material": "Mild Steel",
        "material_grade": "IS 2062 E250",
        "thickness_mm": 2.0,
        "length_mm": 100,
        "width_mm": 100,
        "weight_kg": 1.0,
        "bend_count": 0,
        "hole_count": 0,
        "surface_finish": "Painted",
        "finish_cost_per_part": 0,
        "material_rate_per_kg": 100,
        "cycle_time_min": 0,
        "energy_kwh_per_part": 0,
        "energy_rate_per_kwh": 0,
        "labour_hours": 0,
        "labour_rate_per_hour": 0,
        "overhead_pct": 0,
        "supplier_margin_pct": 0,
        "current_supplier": "Supplier",
        "supplier_region": "India",
        "erp_price": erp_price,
        "annual_volume": 10,
    }


def test_savings_opportunity_only_exists_when_erp_price_exceeds_fair_price() -> None:
    result = calculate_should_cost(
        pd.DataFrame(
            [
                _base_part(erp_price=80),
                _base_part(erp_price=125),
            ]
        )
    )

    assert result.loc[0, "should_cost"] == 100
    assert result.loc[0, "price_gap"] == -20
    assert result.loc[0, "savings_opportunity"] == 0
    assert result.loc[0, "opportunity_status"] == "No savings opportunity"

    assert result.loc[1, "should_cost"] == 100
    assert result.loc[1, "price_gap"] == 25
    assert result.loc[1, "savings_opportunity"] == 250
    assert result.loc[1, "opportunity_status"] == "Savings opportunity"


if __name__ == "__main__":
    test_savings_opportunity_only_exists_when_erp_price_exceeds_fair_price()
    print("Cost model tests passed")
