from __future__ import annotations

import pandas as pd


DRIVER_COLUMNS = {
    "material": "material_cost",
    "energy": "energy_cost",
    "labour": "labour_cost",
    "bends and holes": "process_complexity_cost",
    "surface finish": "surface_finish_cost",
    "overhead": "overhead",
    "template adjustments": "manual_template_adjustment_cost",
    "supplier margin": "supplier_margin",
}


def _money(value: float) -> str:
    return f"INR {value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:,.1f}%"


def _top_driver(row: pd.Series) -> tuple[str, float]:
    drivers = {
        label: float(row.get(column, 0) or 0)
        for label, column in DRIVER_COLUMNS.items()
    }
    label = max(drivers, key=drivers.get)
    return label, drivers[label]


def build_procurement_explanations(parts: pd.DataFrame) -> pd.DataFrame:
    """Explain fair price, ERP price, vendor, savings, BATNA, and negotiation."""
    rows = []
    for _, row in parts.iterrows():
        top_driver, top_driver_value = _top_driver(row)
        erp_price = float(row["erp_price"])
        fair_price = float(row.get("ai_predicted_fair_price", row["should_cost"]))
        should_cost = float(row["should_cost"])
        gap = erp_price - fair_price
        gap_pct = gap / fair_price * 100 if fair_price else 0.0
        annual_volume = float(row["annual_volume"])
        savings = max(gap, 0) * annual_volume
        supplier = row["current_supplier"]

        if gap > 0:
            erp_reason = (
                f"ERP price is high mainly because {top_driver} contributes {_money(top_driver_value)} "
                f"and the purchase price is {_pct(gap_pct)} above the ML fair price."
            )
            negotiation = (
                f"Ask {supplier} to bridge the gap from {_money(erp_price)} toward "
                f"{_money(fair_price)} using the {top_driver} cost evidence; target at least "
                f"{_money(max(gap * 0.6, 0))} per part in the first round."
            )
        else:
            erp_reason = (
                f"ERP price is not above the ML fair price; {top_driver} remains the largest cost driver."
            )
            negotiation = (
                f"Maintain {supplier} pricing, request cost transparency on {top_driver}, and protect the current rate."
            )

        batna_price = min(should_cost * 1.08, fair_price * 1.05)
        batna = (
            f"BATNA: re-quote the cluster or alternate qualified supplier at about {_money(batna_price)} "
            f"per part before accepting any price above {_money(fair_price)}."
        )

        rows.append(
            {
                "part_id": row["part_id"],
                "vendor": supplier,
                "erp_price": erp_price,
                "fair_price": fair_price,
                "should_cost": should_cost,
                "top_price_increase_feature": top_driver,
                "price_gap_pct": gap_pct,
                "savings_opportunity": savings,
                "erp_price_explanation": erp_reason,
                "negotiation_recommendation": negotiation,
                "batna": batna,
                "xai_summary": (
                    f"Fair price {_money(fair_price)} vs ERP {_money(erp_price)} for {supplier}. "
                    f"Main driver: {top_driver}. Savings opportunity: {_money(savings)}."
                ),
            }
        )
    return pd.DataFrame(rows)
