from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.erp_pipeline import clean_erp_data, save_pipeline_outputs


COUNTRY_CODE_TO_NAME = {
    "BE": "Belgium",
    "CN": "China",
    "DE": "Germany",
    "DK": "Denmark",
    "HK": "Hong Kong",
    "HU": "Hungary",
    "IN": "India",
    "JP": "Japan",
    "MX": "Mexico",
    "TH": "Thailand",
    "TW": "Taiwan",
    "US": "USA",
}


def _stable_part_id(description: str, bracket_type: str, material_tag: str) -> str:
    key = "|".join(
        [
            str(description).strip().upper(),
            str(bracket_type).strip().upper(),
            str(material_tag).strip().upper(),
        ]
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()
    return f"BR-{digest}"


def convert_bracket_purchase_data(source: str | Path) -> pd.DataFrame:
    raw = pd.read_excel(source, sheet_name="Bracket Purchase Data")
    raw["Material / Process Tag"] = raw["Material / Process Tag"].fillna("")
    raw["Part Number"] = raw.apply(
        lambda row: _stable_part_id(
            row["Short Text / Description"],
            row["Bracket Type"],
            row["Material / Process Tag"],
        ),
        axis=1,
    )
    raw["Supplier Country"] = (
        raw["Country"].astype(str).str.upper().map(COUNTRY_CODE_TO_NAME).fillna(raw["Country"])
    )

    converted = pd.DataFrame(
        {
            "Part Number": raw["Part Number"],
            "Part Description": raw["Short Text / Description"],
            "Category": raw["Bracket Type"],
            "Supplier Name": raw["Vendor Account Number"],
            "Supplier Country": raw["Supplier Country"],
            "PO Date": pd.to_datetime(raw["Posting Date"]).dt.strftime("%Y-%m-%d"),
            "Quantity": raw["Actual Quantity"],
            "Unit Price": raw["Unit Price (Local)"],
            "Currency": raw["Local Currency"],
            "Total Purchasing Price Local": raw["Total Purchasing Price (Local)"],
            "Original Country Code": raw["Country"],
            "Bracket Type": raw["Bracket Type"],
            "Material Process Tag": raw["Material / Process Tag"],
            "Tooling Flag": raw["Tooling Flag"],
        }
    )
    return converted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import real bracket purchase data into the app ERP schema."
    )
    parser.add_argument(
        "--input",
        default="/Users/chetanshet/Downloads/bracket_purchase_data.xlsx",
        help="Source bracket purchase workbook.",
    )
    parser.add_argument(
        "--output",
        default="data/erp_raw_sample.csv",
        help="ERP raw CSV output used by the Streamlit app.",
    )
    parser.add_argument(
        "--processed-output-dir",
        default="data/processed",
        help="Directory for cleaned ERP outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    converted = convert_bracket_purchase_data(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted.to_csv(output_path, index=False)

    result = clean_erp_data(converted)
    save_pipeline_outputs(result, args.processed_output_dir)

    print(f"Imported ERP rows: {len(converted)}")
    print(f"Cleaned ERP rows: {len(result.cleaned_data)}")
    print(f"Raw ERP output: {output_path}")
    print(f"Processed output directory: {args.processed_output_dir}")


if __name__ == "__main__":
    main()
