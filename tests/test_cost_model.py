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

    assert result.loc[0, "should_cost"] > 100
    assert result.loc[0, "price_gap"] < 0
    assert result.loc[0, "savings_opportunity"] == 0
    assert result.loc[0, "opportunity_status"] == "No savings opportunity"

    assert result.loc[1, "should_cost"] < 125
    assert result.loc[1, "price_gap"] > 0
    assert result.loc[1, "savings_opportunity"] == result.loc[1, "price_gap"] * 10
    assert result.loc[1, "opportunity_status"] == "Savings opportunity"


def test_material_cost_uses_weight_and_market_adjusted_steel_rate() -> None:
    result = calculate_should_cost(
        pd.DataFrame([_base_part(erp_price=500)]),
        material_rate_factor=1.25,
    )

    assert round(result.loc[0, "market_material_rate_per_kg"], 3) == 126.875
    assert round(result.loc[0, "material_cost"], 3) == 126.875


def test_regional_rates_drive_energy_labour_and_machine_costs() -> None:
    part = _base_part(erp_price=500)
    part.update(
        {
            "supplier_region": "Vietnam",
            "energy_kwh_per_part": 2,
            "labour_hours": 1,
            "bend_count": 1,
            "hole_count": 2,
        }
    )
    result = calculate_should_cost(pd.DataFrame([part]))

    assert result.loc[0, "predicted_energy_rate_per_kwh"] == 7.8
    assert result.loc[0, "energy_cost"] == 15.6
    assert result.loc[0, "predicted_labour_rate_per_hour"] == 340
    assert result.loc[0, "labour_cost"] == 340
    assert result.loc[0, "machine_rate_per_hour"] == 620
    assert result.loc[0, "process_complexity_cost"] > 0


def test_qualified_savings_means_erp_price_is_above_predicted_fair_price() -> None:
    result = calculate_should_cost(pd.read_csv("data/sample_parts.csv"))
    savings_parts = result[result["savings_opportunity"] > 0]

    assert not savings_parts.empty
    assert (savings_parts["erp_price"] > savings_parts["should_cost"]).all()


if __name__ == "__main__":
    test_savings_opportunity_only_exists_when_erp_price_exceeds_fair_price()
    test_material_cost_uses_weight_and_market_adjusted_steel_rate()
    test_regional_rates_drive_energy_labour_and_machine_costs()
    test_qualified_savings_means_erp_price_is_above_predicted_fair_price()
    print("Cost model tests passed")
