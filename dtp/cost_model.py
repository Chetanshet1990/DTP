from __future__ import annotations

import pandas as pd


PRICE_GAP_THRESHOLD = 5.0


REGION_COST_ASSUMPTIONS = {
    "India": {
        "energy_rate_per_kwh": 8.5,
        "labour_rate_per_hour": 390.0,
        "machine_rate_per_hour": 650.0,
        "overhead_pct": 22.0,
    },
    "Vietnam": {
        "energy_rate_per_kwh": 7.8,
        "labour_rate_per_hour": 340.0,
        "machine_rate_per_hour": 620.0,
        "overhead_pct": 20.0,
    },
    "China": {
        "energy_rate_per_kwh": 7.5,
        "labour_rate_per_hour": 460.0,
        "machine_rate_per_hour": 720.0,
        "overhead_pct": 24.0,
    },
    "USA": {
        "energy_rate_per_kwh": 10.0,
        "labour_rate_per_hour": 1900.0,
        "machine_rate_per_hour": 2400.0,
        "overhead_pct": 35.0,
    },
}

DEFAULT_REGION_COSTS = REGION_COST_ASSUMPTIONS["India"]

MATERIAL_GRADE_FACTORS = {
    "IS 2062 E250": 1.00,
    "IS 2062 E350": 1.05,
    "CRCA IS 513": 1.08,
    "GI G90": 1.12,
    "SS304": 1.18,
}

SURFACE_FINISH_COST_PER_M2 = {
    "Painted": 180.0,
    "Powder coated": 260.0,
    "Zinc plated": 220.0,
    "Passivated": 240.0,
}

MIN_INDUSTRY_MARGIN_PCT = {
    "Bracket": 8.0,
    "Mounting plate": 8.0,
    "Cover / panel": 9.0,
    "Fabricated assembly": 10.0,
}

BEND_MINUTES = 1.8
HOLE_MINUTES = 0.35


def _map_series(values: pd.Series, mapping: dict[str, float], default: float) -> pd.Series:
    return values.map(mapping).fillna(default).astype(float)


def _region_assumption(regions: pd.Series, field: str) -> pd.Series:
    mapping = {
        region: assumptions[field]
        for region, assumptions in REGION_COST_ASSUMPTIONS.items()
    }
    return _map_series(regions, mapping, DEFAULT_REGION_COSTS[field])


def calculate_should_cost(parts: pd.DataFrame, material_rate_factor: float = 1.0) -> pd.DataFrame:
    result = parts.copy()
    numeric_columns = [
        "weight_kg",
        "thickness_mm",
        "length_mm",
        "width_mm",
        "bend_count",
        "hole_count",
        "finish_cost_per_part",
        "material_rate_per_kg",
        "energy_kwh_per_part",
        "energy_rate_per_kwh",
        "labour_hours",
        "labour_rate_per_hour",
        "overhead_pct",
        "supplier_margin_pct",
        "erp_price",
        "annual_volume",
    ]
    result[numeric_columns] = result[numeric_columns].apply(pd.to_numeric, errors="coerce")

    result["blank_area_m2"] = (result["length_mm"] * result["width_mm"]) / 1_000_000
    result["grade_factor"] = _map_series(
        result["material_grade"],
        MATERIAL_GRADE_FACTORS,
        1.0,
    )
    result["thickness_factor"] = 1 + (result["thickness_mm"].clip(lower=1.0) - 1.0) * 0.015
    result["market_material_rate_per_kg"] = (
        result["material_rate_per_kg"] * material_rate_factor
        * result["grade_factor"]
        * result["thickness_factor"]
    )
    result["material_cost"] = result["weight_kg"] * result["market_material_rate_per_kg"]
    result["predicted_energy_rate_per_kwh"] = _region_assumption(
        result["supplier_region"],
        "energy_rate_per_kwh",
    )
    result["energy_cost"] = result["energy_kwh_per_part"] * result["predicted_energy_rate_per_kwh"]
    result["predicted_labour_rate_per_hour"] = _region_assumption(
        result["supplier_region"],
        "labour_rate_per_hour",
    )
    result["labour_cost"] = result["labour_hours"] * result["predicted_labour_rate_per_hour"]
    result["machine_rate_per_hour"] = _region_assumption(
        result["supplier_region"],
        "machine_rate_per_hour",
    )
    result["operation_minutes"] = (
        result["bend_count"] * BEND_MINUTES
        + result["hole_count"] * HOLE_MINUTES
    ) * result["thickness_factor"]
    result["bend_cost"] = (
        result["bend_count"] * BEND_MINUTES * result["thickness_factor"]
        * result["machine_rate_per_hour"] / 60
    )
    result["piercing_cost"] = (
        result["hole_count"] * HOLE_MINUTES * result["thickness_factor"]
        * result["machine_rate_per_hour"] / 60
    )
    result["process_complexity_cost"] = result["bend_cost"] + result["piercing_cost"]
    result["surface_finish_rate_per_m2"] = _map_series(
        result["surface_finish"],
        SURFACE_FINISH_COST_PER_M2,
        0.0,
    )
    result["surface_finish_cost"] = (
        result["blank_area_m2"] * result["surface_finish_rate_per_m2"]
    )
    result["conversion_cost"] = (
        result["energy_cost"]
        + result["labour_cost"]
        + result["process_complexity_cost"]
        + result["surface_finish_cost"]
    )
    result["predicted_overhead_pct"] = _region_assumption(
        result["supplier_region"],
        "overhead_pct",
    )
    result["overhead"] = result["conversion_cost"] * result["predicted_overhead_pct"] / 100
    result["cost_before_margin"] = (
        result["material_cost"]
        + result["energy_cost"]
        + result["labour_cost"]
        + result["process_complexity_cost"]
        + result["surface_finish_cost"]
        + result["overhead"]
    )
    result["predicted_supplier_margin_pct"] = _map_series(
        result["category"],
        MIN_INDUSTRY_MARGIN_PCT,
        9.0,
    )
    result["supplier_margin"] = (
        result["cost_before_margin"] * result["predicted_supplier_margin_pct"] / 100
    )
    result["should_cost"] = result["cost_before_margin"] + result["supplier_margin"]
    result["price_gap"] = result["erp_price"] - result["should_cost"]
    result["price_gap_pct"] = result["price_gap"] / result["should_cost"] * 100

    # Savings exist only when the supplier/ERP price is higher than fair price.
    result["savings_opportunity"] = result["price_gap"].clip(lower=0) * result["annual_volume"]
    result["annual_opportunity"] = result["savings_opportunity"]
    result["opportunity_status"] = result["savings_opportunity"].apply(
        lambda value: "Savings opportunity" if value > 0 else "No savings opportunity"
    )
    result["gap_status"] = result["price_gap_pct"].apply(
        lambda value: "Review" if value > PRICE_GAP_THRESHOLD else "OK"
    )
    return result
