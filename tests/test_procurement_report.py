from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.procurement_report import build_procurement_report


def test_detailed_procurement_report_contains_all_decision_sections() -> None:
    explanation = {
        "part_id": "SM-TEST",
        "vendor": "Supplier A",
        "erp_price": 1500.0,
        "fair_price": 1200.0,
        "should_cost": 1100.0,
        "price_gap_pct": 25.0,
        "savings_opportunity": 300000.0,
        "top_price_increase_feature": "material",
        "erp_price_explanation": "ERP price is above the ML fair price due to material cost.",
        "negotiation_recommendation": "Negotiate toward the fair price using material evidence.",
        "batna": "BATNA: obtain a validated alternate quotation.",
        "xai_summary": "The model identifies material as the strongest price driver.",
    }
    part = {
        "part_id": "SM-TEST",
        "part_name": "Test bracket",
        "category": "Bracket",
        "supplier_region": "India",
        "annual_volume": 1000,
        "prediction_confidence": "High",
        "label_quality_status": "Clean",
        "material_cost": 600.0,
        "energy_cost": 50.0,
        "labour_cost": 120.0,
        "process_complexity_cost": 80.0,
        "surface_finish_cost": 40.0,
        "overhead": 100.0,
        "manual_template_adjustment_cost": 20.0,
        "supplier_margin": 90.0,
        "shap_top_feature": "material_grade",
        "shap_procurement_explanation": "Material grade increases predicted fair price.",
    }

    report = build_procurement_report(explanation, part)
    assert report.startswith(b"%PDF")

    reader = PdfReader(BytesIO(report))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for expected_heading in [
        "ERP price explanation",
        "Negotiation recommendation",
        "BATNA and escalation path",
        "Explainable-AI interpretation",
        "Decision checklist",
    ]:
        assert expected_heading in extracted_text


if __name__ == "__main__":
    test_detailed_procurement_report_contains_all_decision_sections()
    print("Procurement report tests passed")
