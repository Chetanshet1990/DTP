from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.erp_pipeline import clean_erp_data


def test_clean_erp_data_anonymizes_and_normalizes_currency() -> None:
    raw = pd.DataFrame(
        [
            {
                "Part Number": "SM-1",
                "Part Description": "Steel bracket",
                "Category": "Bracket",
                "Supplier Name": "Real Supplier Ltd",
                "Supplier Country": "India",
                "PO Date": "2024-01-15",
                "Quantity": "10",
                "Unit Price": "100",
                "Currency": "INR",
            },
            {
                "Part Number": "SM-2",
                "Part Description": "Control cabinet mounting plate",
                "Category": "Mounting Plate",
                "Supplier Name": "Another Supplier",
                "Supplier Country": "Germany",
                "PO Date": "2024-02-20",
                "Quantity": "5",
                "Unit Price": "10",
                "Currency": "EUR",
            },
        ]
    )

    result = clean_erp_data(raw)

    assert list(result.cleaned_data["supplier_id"]) == ["Supplier_2", "Supplier_1"]
    assert "Supplier Name" not in result.cleaned_data.columns
    assert result.cleaned_data.loc[0, "unit_price_usd"] == 1.2
    assert result.cleaned_data.loc[1, "unit_price_usd"] == 10.8
    assert result.cleaned_data.loc[0, "category"] == "Bracket"
    assert result.cleaned_data.loc[1, "category"] == "Mounting plate"


def test_clean_erp_data_accepts_review3_generated_schema() -> None:
    raw = pd.DataFrame(
        [
            {
                "po_number": "PO-1",
                "po_date": "2026-03-01",
                "part_id": "SM-1001",
                "part_description": "Mounting bracket",
                "category": "Bracket",
                "supplier_name": "SteelWorks",
                "country": "India",
                "currency": "INR",
                "unit_price": 600,
                "quantity": 100,
            }
        ]
    )

    result = clean_erp_data(raw)

    assert len(result.cleaned_data) == 1
    assert result.cleaned_data.loc[0, "part_id"] == "SM-1001"
    assert result.cleaned_data.loc[0, "unit_price_usd"] == 7.2


if __name__ == "__main__":
    test_clean_erp_data_anonymizes_and_normalizes_currency()
    test_clean_erp_data_accepts_review3_generated_schema()
    print("ERP pipeline tests passed")
