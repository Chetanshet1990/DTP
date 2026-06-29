from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import random


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

FIELDNAMES = [
    "part_id",
    "part_name",
    "category",
    "material",
    "material_grade",
    "thickness_mm",
    "length_mm",
    "width_mm",
    "weight_kg",
    "bend_count",
    "hole_count",
    "surface_finish",
    "finish_cost_per_part",
    "material_rate_per_kg",
    "cycle_time_min",
    "energy_kwh_per_part",
    "energy_rate_per_kwh",
    "labour_hours",
    "labour_rate_per_hour",
    "overhead_pct",
    "supplier_margin_pct",
    "current_supplier",
    "supplier_region",
    "erp_price",
    "annual_volume",
]

CATEGORIES = [
    ("Bracket", "Mild Steel", "IS 2062 E250"),
    ("Bracket", "Mild Steel", "IS 2062 E350"),
    ("Mounting plate", "CRCA Steel", "CRCA IS 513"),
    ("Cover / panel", "Galvanized Steel", "GI G90"),
    ("Fabricated assembly", "Stainless Steel", "SS304"),
]
FINISHES = ["Painted", "Powder coated", "Zinc plated", "Passivated"]
SUPPLIERS = [
    ("SteelWorks", "India"),
    ("PlatePro", "India"),
    ("FabriMax", "Vietnam"),
    ("DragonSheet", "China"),
    ("PrecisionPanel", "USA"),
    ("BendCraft", "India"),
    ("AsiaForm", "Vietnam"),
]
REGION_RATES = {
    "India": (8.5, 390),
    "Vietnam": (7.8, 340),
    "China": (7.5, 460),
    "USA": (10.0, 1900),
}


def _part_name(category: str, index: int) -> str:
    prefix = {
        "Bracket": "Mounting bracket",
        "Mounting plate": "Control plate",
        "Cover / panel": "Access cover",
        "Fabricated assembly": "Welded support",
    }[category]
    return f"{prefix} {index:03d}"


def generate_parts(count: int = 120) -> list[dict[str, object]]:
    rng = random.Random(42)
    rows = []
    for index in range(1, count + 1):
        category, material, grade = rng.choice(CATEGORIES)
        supplier, region = rng.choice(SUPPLIERS)
        energy_rate, labour_rate = REGION_RATES[region]
        thickness = rng.choice([1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0])
        length = rng.randint(120, 950)
        width = rng.randint(80, 620)
        area_m2 = length * width / 1_000_000
        density_factor = 7.85
        weight = max(0.18, area_m2 * thickness * density_factor * rng.uniform(0.75, 1.08))
        bend_count = rng.randint(0, 10)
        hole_count = rng.randint(2, 28)
        finish = rng.choice(FINISHES)
        material_rate = {
            "IS 2062 E250": 78,
            "IS 2062 E350": 82,
            "CRCA IS 513": 86,
            "GI G90": 92,
            "SS304": 145,
        }[grade] * rng.uniform(0.95, 1.08)
        cycle_time = 6 + bend_count * 1.8 + hole_count * 0.35 + weight * 2.2
        energy = 0.22 + weight * 0.24 + bend_count * 0.025 + hole_count * 0.006
        labour_hours = cycle_time / 60 * rng.uniform(0.9, 1.2)
        base_price = (
            weight * material_rate * 1.1
            + energy * energy_rate
            + labour_hours * labour_rate
            + bend_count * 18
            + hole_count * 4
            + area_m2 * 230
        )
        supplier_markup = rng.uniform(1.03, 1.24)
        if index % 9 == 0:
            supplier_markup += rng.uniform(0.16, 0.34)
        erp_price = base_price * supplier_markup
        rows.append(
            {
                "part_id": f"SM-{1000 + index}",
                "part_name": _part_name(category, index),
                "category": category,
                "material": material,
                "material_grade": grade,
                "thickness_mm": round(thickness, 1),
                "length_mm": length,
                "width_mm": width,
                "weight_kg": round(weight, 2),
                "bend_count": bend_count,
                "hole_count": hole_count,
                "surface_finish": finish,
                "finish_cost_per_part": round(area_m2 * 230, 2),
                "material_rate_per_kg": round(material_rate, 2),
                "cycle_time_min": round(cycle_time, 1),
                "energy_kwh_per_part": round(energy, 2),
                "energy_rate_per_kwh": energy_rate,
                "labour_hours": round(labour_hours, 2),
                "labour_rate_per_hour": labour_rate,
                "overhead_pct": rng.choice([20, 22, 24, 27, 35]),
                "supplier_margin_pct": rng.choice([9, 10, 11, 12, 13]),
                "current_supplier": supplier,
                "supplier_region": region,
                "erp_price": round(erp_price, 2),
                "annual_volume": rng.randint(600, 18000),
            }
        )
    return rows


def generate_erp(parts: list[dict[str, object]], rows_per_part: int = 4) -> list[dict[str, object]]:
    rng = random.Random(84)
    currencies = {"India": "INR", "Vietnam": "USD", "China": "USD", "USA": "USD"}
    today = date(2026, 6, 29)
    rows = []
    for part in parts:
        for offset in range(rows_per_part):
            po_date = today - timedelta(days=30 * (rows_per_part - offset) + rng.randint(0, 14))
            currency = currencies[str(part["supplier_region"])]
            unit_price = float(part["erp_price"]) * rng.uniform(0.94, 1.08)
            if currency == "USD":
                unit_price = unit_price / 83.0
            rows.append(
                {
                    "po_number": f"PO-R3-{part['part_id']}-{offset + 1}",
                    "po_date": po_date.isoformat(),
                    "part_id": part["part_id"],
                    "part_description": part["part_name"],
                    "category": part["category"],
                    "supplier_name": part["current_supplier"],
                    "country": part["supplier_region"],
                    "currency": currency,
                    "unit_price": round(unit_price, 2),
                    "quantity": rng.randint(50, 900),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parts = generate_parts()
    erp_rows = generate_erp(parts)
    write_csv(DATA_DIR / "sample_parts.csv", parts, FIELDNAMES)
    write_csv(
        DATA_DIR / "erp_raw_sample.csv",
        erp_rows,
        [
            "po_number",
            "po_date",
            "part_id",
            "part_description",
            "category",
            "supplier_name",
            "country",
            "currency",
            "unit_price",
            "quantity",
        ],
    )
    print(f"Wrote {len(parts)} parts and {len(erp_rows)} ERP rows")


if __name__ == "__main__":
    main()
