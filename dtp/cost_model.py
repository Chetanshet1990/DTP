from __future__ import annotations

import pandas as pd


PRICE_GAP_THRESHOLD = 5.0


def calculate_should_cost(parts: pd.DataFrame) -> pd.DataFrame:
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
    result["material_cost"] = result["weight_kg"] * result["material_rate_per_kg"]
    result["energy_cost"] = result["energy_kwh_per_part"] * result["energy_rate_per_kwh"]
    result["labour_cost"] = result["labour_hours"] * result["labour_rate_per_hour"]
    result["bend_cost"] = result["bend_count"] * 12.0
    result["piercing_cost"] = result["hole_count"] * 3.0
    result["process_complexity_cost"] = result["bend_cost"] + result["piercing_cost"]
    result["surface_finish_cost"] = result["finish_cost_per_part"]
    result["conversion_cost"] = (
        result["energy_cost"]
        + result["labour_cost"]
        + result["process_complexity_cost"]
        + result["surface_finish_cost"]
    )
    result["overhead"] = result["conversion_cost"] * result["overhead_pct"] / 100
    result["cost_before_margin"] = (
        result["material_cost"]
        + result["energy_cost"]
        + result["labour_cost"]
        + result["process_complexity_cost"]
        + result["surface_finish_cost"]
        + result["overhead"]
    )
    result["supplier_margin"] = result["cost_before_margin"] * result["supplier_margin_pct"] / 100
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
