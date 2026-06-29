from __future__ import annotations

import pandas as pd


# REVIEW EXPLANATION:
# This file is the Cost Digital Twin. It converts drawing/part attributes into
# an explainable should-cost by adding material, conversion, overhead, manual
# template adjustments, and supplier margin.

PRICE_GAP_THRESHOLD = 5.0


REGION_COST_ASSUMPTIONS = {
    # Regional assumptions approximate energy, labour, machine, and overhead cost
    # differences by supplier manufacturing location.
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
    # Material grade factors adjust the base steel rate. Example: SS304 is costlier
    # than mild steel, so its factor is higher.
    "IS 2062 E250": 1.00,
    "IS 2062 E350": 1.05,
    "CRCA IS 513": 1.08,
    "GI G90": 1.12,
    "SS304": 1.18,
}

SURFACE_FINISH_COST_PER_M2 = {
    # Surface finishes add real conversion cost in sheet metal manufacturing.
    "Painted": 180.0,
    "Powder coated": 260.0,
    "Zinc plated": 220.0,
    "Passivated": 240.0,
}

MIN_INDUSTRY_MARGIN_PCT = {
    # The model uses minimum category-level margin assumptions instead of trusting
    # any supplier-entered margin value.
    "Bracket": 8.0,
    "Mounting plate": 8.0,
    "Cover / panel": 9.0,
    "Fabricated assembly": 10.0,
}

BEND_MINUTES = 1.8
HOLE_MINUTES = 0.35
DEFAULT_REJECTION_PCT = 2.0
DEFAULT_TOOL_MAINTENANCE_PCT = 0.5
DEFAULT_PACKING_FORWARDING_PCT = 2.0


def _map_series(values: pd.Series, mapping: dict[str, float], default: float) -> pd.Series:
    """Map text categories to numeric assumptions with a safe default."""
    return values.map(mapping).fillna(default).astype(float)


def _region_assumption(regions: pd.Series, field: str) -> pd.Series:
    """Return one regional cost assumption column for each supplier region."""
    mapping = {
        region: assumptions[field]
        for region, assumptions in REGION_COST_ASSUMPTIONS.items()
    }
    return _map_series(regions, mapping, DEFAULT_REGION_COSTS[field])


def calculate_should_cost(parts: pd.DataFrame, material_rate_factor: float = 1.0) -> pd.DataFrame:
    """Calculate should-cost and price-gap fields for every part."""
    result = parts.copy()

    # Optional industry-costing fields are filled with defaults so the demo runs
    # even when a user uploads a simpler part master without full costing inputs.
    optional_numeric_defaults = {
        "blank_weight_kg": pd.NA,
        "scrap_weight_kg": pd.NA,
        "scrap_rate_per_kg": 0.0,
        "scrap_recovery_pct": 95.0,
        "rejection_pct": DEFAULT_REJECTION_PCT,
        "tool_maintenance_pct": DEFAULT_TOOL_MAINTENANCE_PCT,
        "packing_forwarding_pct": DEFAULT_PACKING_FORWARDING_PCT,
        "tooling_cost": 0.0,
        "tooling_cost_per_part": pd.NA,
    }
    for column, default in optional_numeric_defaults.items():
        if column not in result.columns:
            result[column] = default

    # Convert all calculation inputs to numeric. Invalid strings become NaN and
    # are caught earlier by the Streamlit validation for uploaded data.
    numeric_columns = [
        "weight_kg",
        "blank_weight_kg",
        "scrap_weight_kg",
        "scrap_rate_per_kg",
        "scrap_recovery_pct",
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
        "rejection_pct",
        "tool_maintenance_pct",
        "packing_forwarding_pct",
        "tooling_cost",
        "tooling_cost_per_part",
        "erp_price",
        "annual_volume",
    ]
    result[numeric_columns] = result[numeric_columns].apply(pd.to_numeric, errors="coerce")

    # MATERIAL COST:
    # base material rate x live market factor x grade factor x thickness factor.
    # Scrap recovery is subtracted so the material estimate is closer to an
    # industry costing sheet instead of a simple weight-only formula.
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
    result["blank_weight_kg"] = result["blank_weight_kg"].fillna(result["weight_kg"])
    result["raw_material_cost_gross"] = (
        result["blank_weight_kg"] * result["market_material_rate_per_kg"]
    )
    result["scrap_weight_kg"] = result["scrap_weight_kg"].fillna(
        (result["blank_weight_kg"] - result["weight_kg"]).clip(lower=0)
    )
    result["scrap_recovery"] = (
        result["scrap_weight_kg"]
        * result["scrap_rate_per_kg"]
        * result["scrap_recovery_pct"].clip(lower=0) / 100
    )
    result["material_cost"] = (
        result["raw_material_cost_gross"] - result["scrap_recovery"]
    ).clip(lower=0)

    # CONVERSION COST:
    # energy, labour, machine time for bends/holes, and surface finish.
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

    # OVERHEAD AND MANUAL TEMPLATE ADJUSTMENTS:
    # These mirror practical costing templates: rejection, tool maintenance,
    # packing/forwarding, and tooling amortization.
    result["predicted_overhead_pct"] = _region_assumption(
        result["supplier_region"],
        "overhead_pct",
    )
    result["overhead"] = result["conversion_cost"] * result["predicted_overhead_pct"] / 100
    manual_template_base = result["material_cost"] + result["conversion_cost"]
    result["rejection_allowance"] = manual_template_base * result["rejection_pct"] / 100
    result["tool_maintenance_cost"] = (
        result["conversion_cost"] * result["tool_maintenance_pct"] / 100
    )
    result["packing_forwarding_cost"] = (
        manual_template_base * result["packing_forwarding_pct"] / 100
    )
    result["tooling_amortization_cost"] = result["tooling_cost_per_part"].fillna(
        result["tooling_cost"] / result["annual_volume"].replace(0, pd.NA)
    ).fillna(0)
    result["manual_template_adjustment_cost"] = (
        result["rejection_allowance"]
        + result["tool_maintenance_cost"]
        + result["packing_forwarding_cost"]
        + result["tooling_amortization_cost"]
    )

    # FINAL SHOULD-COST:
    # Cost before margin plus minimum industry supplier margin.
    result["cost_before_margin"] = (
        result["material_cost"]
        + result["energy_cost"]
        + result["labour_cost"]
        + result["process_complexity_cost"]
        + result["surface_finish_cost"]
        + result["overhead"]
        + result["manual_template_adjustment_cost"]
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

    # BUSINESS COMPARISON:
    # Positive gap means ERP/current supplier price is above should-cost.
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
