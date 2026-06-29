from __future__ import annotations

from dtp.drawing_extractor import extract_specs_from_text


def test_extract_specs_from_manufacturing_drawing_text() -> None:
    result = extract_specs_from_text(
        """
        PART: CONTROL BRACKET
        MATERIAL: IS 2062 E250
        THK: 3.0 mm
        LENGTH: 220 mm
        WIDTH: 140 mm
        BENDS: 4
        HOLES: 6
        FINISH: Powder coated
        """,
        file_name="sample_drawing.txt",
    )

    assert result.confidence == "High"
    assert result.extracted_specs["material_grade"] == "IS 2062 E250"
    assert result.extracted_specs["thickness_mm"] == 3.0
    assert result.extracted_specs["length_mm"] == 220.0
    assert result.extracted_specs["width_mm"] == 140.0
    assert result.extracted_specs["bend_count"] == 4
    assert result.extracted_specs["hole_count"] == 6
    assert result.extracted_specs["surface_finish"] == "Powder coated"
