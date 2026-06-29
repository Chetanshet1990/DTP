from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# REVIEW EXPLANATION:
# This file is the ERP data preparation layer. It takes raw purchase records
# from CSV/Excel and converts them into a clean, anonymized schema that the
# dashboard can safely use for procurement analytics.

REQUIRED_ERP_COLUMNS = [
    "Part Number",
    "Part Description",
    "Category",
    "Supplier Name",
    "Supplier Country",
    "PO Date",
    "Quantity",
    "Unit Price",
    "Currency",
]


CURRENCY_TO_USD = {
    # These fixed rates are demo conversion factors. In a production system this
    # would come from dated FX tables so each PO is converted using its PO date.
    "USD": 1.0,
    "INR": 0.012,
    "EUR": 1.08,
    "GBP": 1.25,
    "CNY": 0.14,
    "JPY": 0.0067,
    "MXN": 0.059,
    "THB": 0.027,
    "DKK": 0.145,
    "HKD": 0.128,
    "TWD": 0.031,
}


COUNTRY_TO_REGION = {
    # Country-to-region mapping is used for supplier benchmarking and analytics.
    # It is separate from the cost model's manufacturing-region assumptions.
    "India": "South Asia",
    "China": "East Asia",
    "Vietnam": "Southeast Asia",
    "Mexico": "North America",
    "USA": "North America",
    "Germany": "Europe",
    "Poland": "Europe",
    "Belgium": "Europe",
    "Denmark": "Europe",
    "Hong Kong": "East Asia",
    "Hungary": "Europe",
    "Japan": "East Asia",
    "Thailand": "Southeast Asia",
    "Taiwan": "East Asia",
}


CATEGORY_KEYWORDS = {
    # If ERP category text is inconsistent, the description is used to infer a
    # simple sheet-metal category such as bracket, plate, cover, or assembly.
    "Bracket": [
        "bracket",
    ],
    "Mounting plate": [
        "mounting plate",
        "base plate",
        "plate",
    ],
    "Cover / panel": [
        "cover",
        "panel",
        "guard",
        "enclosure",
    ],
    "Fabricated assembly": [
        "fabricated",
        "fabrication",
        "assembly",
        "welded",
        "frame",
        "tray",
    ],
}


FINAL_ERP_COLUMNS = [
    "part_id",
    "description",
    "category",
    "supplier_id",
    "country",
    "region",
    "po_date",
    "quantity",
    "unit_price",
    "currency",
    "unit_price_usd",
    "year",
    "month",
]


@dataclass(frozen=True)
class PipelineResult:
    cleaned_data: pd.DataFrame
    supplier_map: pd.DataFrame
    data_quality: dict[str, int]


def load_erp_file(path: str | Path) -> pd.DataFrame:
    """Read either Excel or CSV ERP data into a pandas DataFrame."""
    source = Path(path)
    if source.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    return pd.read_csv(source)


def validate_erp_columns(raw_data: pd.DataFrame) -> None:
    """Stop early if mandatory ERP columns are missing."""
    missing = [column for column in REQUIRED_ERP_COLUMNS if column not in raw_data.columns]
    if missing:
        raise ValueError(f"Missing required ERP columns: {', '.join(missing)}")


def normalize_text(value: object) -> str:
    """Standardize text values so duplicates and mappings behave consistently."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def map_category(raw_category: object, description: object) -> str:
    """Map noisy ERP category/description text to the project part categories."""
    combined = f"{normalize_text(raw_category)} {normalize_text(description)}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in combined for keyword in keywords):
            return category
    return "Other"


def anonymize_suppliers(suppliers: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """Replace supplier names with Supplier_1, Supplier_2, etc. for privacy."""
    normalized = suppliers.map(normalize_text)
    unique_suppliers = sorted(supplier for supplier in normalized.dropna().unique() if supplier)
    mapping = {
        supplier: f"Supplier_{index + 1}"
        for index, supplier in enumerate(unique_suppliers)
    }
    supplier_map = pd.DataFrame(
        {
            "supplier_name": list(mapping.keys()),
            "supplier_id": list(mapping.values()),
        }
    )
    return normalized.map(mapping).fillna("Supplier_Unknown"), supplier_map


def clean_erp_data(raw_data: pd.DataFrame) -> PipelineResult:
    """Main ERP pipeline used by both scripts and the Streamlit app."""
    validate_erp_columns(raw_data)
    data = raw_data.copy()
    before_rows = len(data)

    # 1) Normalize text columns before duplicate checks and mappings.
    for column in ["Part Number", "Part Description", "Category", "Supplier Name", "Supplier Country", "Currency"]:
        data[column] = data[column].map(normalize_text)

    # 2) Remove exact duplicate purchase rows and record how many were removed.
    data = data.drop_duplicates()
    duplicate_rows_removed = before_rows - len(data)

    # 3) Convert dates, quantity, and price into proper numeric/date types.
    data["PO Date"] = pd.to_datetime(data["PO Date"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["Unit Price"] = pd.to_numeric(data["Unit Price"], errors="coerce")
    data["Currency"] = data["Currency"].str.upper()

    missing_required_rows = int(
        data[
            [
                "Part Number",
                "Part Description",
                "Supplier Name",
                "Supplier Country",
                "PO Date",
                "Quantity",
                "Unit Price",
                "Currency",
            ]
        ]
        .isna()
        .any(axis=1)
        .sum()
    )
    # 4) Remove unusable rows: missing fields, returns/credits, zero quantities,
    #    zero prices, and currencies that are not supported in the demo mapping.
    data = data.dropna(
        subset=[
            "Part Number",
            "Part Description",
            "Supplier Name",
            "Supplier Country",
            "PO Date",
            "Quantity",
            "Unit Price",
            "Currency",
        ]
    )
    data = data[(data["Quantity"] > 0) & (data["Unit Price"] > 0)]

    unknown_currency_rows = int((~data["Currency"].isin(CURRENCY_TO_USD)).sum())
    data = data[data["Currency"].isin(CURRENCY_TO_USD)]

    # 5) Create analysis fields: anonymized supplier, mapped category,
    #    USD-normalized price, calendar fields, and broad supplier region.
    supplier_ids, supplier_map = anonymize_suppliers(data["Supplier Name"])
    data["supplier_id"] = supplier_ids
    data["category_mapped"] = data.apply(
        lambda row: map_category(row["Category"], row["Part Description"]),
        axis=1,
    )
    data["unit_price_usd"] = data["Unit Price"] * data["Currency"].map(CURRENCY_TO_USD)
    data["year"] = data["PO Date"].dt.year
    data["month"] = data["PO Date"].dt.month
    data["region"] = data["Supplier Country"].map(COUNTRY_TO_REGION).fillna("Other")

    cleaned = pd.DataFrame(
        {
            "part_id": data["Part Number"],
            "description": data["Part Description"],
            "category": data["category_mapped"],
            "supplier_id": data["supplier_id"],
            "country": data["Supplier Country"],
            "region": data["region"],
            "po_date": data["PO Date"].dt.strftime("%Y-%m-%d"),
            "quantity": data["Quantity"],
            "unit_price": data["Unit Price"],
            "currency": data["Currency"],
            "unit_price_usd": data["unit_price_usd"].round(4),
            "year": data["year"],
            "month": data["month"],
        }
    )

    # Data-quality counts are exported so the review can show what happened to
    # the raw file. Current sample: 97 source rows -> 90 clean usable rows.
    quality = {
        "source_rows": before_rows,
        "duplicate_rows_removed": duplicate_rows_removed,
        "missing_required_rows_removed": missing_required_rows,
        "unknown_currency_rows_removed": unknown_currency_rows,
        "clean_rows": len(cleaned),
    }

    return PipelineResult(
        cleaned_data=cleaned[FINAL_ERP_COLUMNS],
        supplier_map=supplier_map,
        data_quality=quality,
    )


def save_pipeline_outputs(result: PipelineResult, output_dir: str | Path) -> None:
    """Write cleaned ERP data, supplier map, and quality report as CSV files."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    result.cleaned_data.to_csv(target / "erp_cleaned.csv", index=False)
    result.supplier_map.to_csv(target / "supplier_anonymization_map.csv", index=False)
    pd.DataFrame([result.data_quality]).to_csv(target / "erp_data_quality_report.csv", index=False)
