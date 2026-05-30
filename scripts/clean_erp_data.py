from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.erp_pipeline import clean_erp_data, load_erp_file, save_pipeline_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean and anonymize ERP procurement data.")
    parser.add_argument(
        "--input",
        default="data/erp_raw_sample.csv",
        help="Raw ERP CSV/XLSX file path.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for cleaned ERP outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_data = load_erp_file(args.input)
    result = clean_erp_data(raw_data)
    save_pipeline_outputs(result, args.output_dir)

    output_dir = Path(args.output_dir)
    print(f"Cleaned ERP rows: {len(result.cleaned_data)}")
    print(f"Cleaned data: {output_dir / 'erp_cleaned.csv'}")
    print(f"Supplier map: {output_dir / 'supplier_anonymization_map.csv'}")
    print(f"Quality report: {output_dir / 'erp_data_quality_report.csv'}")


if __name__ == "__main__":
    main()
