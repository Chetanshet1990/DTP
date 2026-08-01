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
        WEIGHT: 1.85 kg
        BENDS: 4
        HOLES: 6
        FINISH: Powder coated
        """,
        file_name="sample_drawing.txt",
    )

    assert result.confidence == "High"
    assert result.extracted_specs["category"] == "Bracket"
    assert result.extracted_specs["material"] == "Mild Steel"
    assert result.extracted_specs["material_grade"] == "IS 2062 E250"
    assert result.extracted_specs["thickness_mm"] == 3.0
    assert result.extracted_specs["length_mm"] == 220.0
    assert result.extracted_specs["width_mm"] == 140.0
    assert result.extracted_specs["weight_kg"] == 1.85
    assert result.extracted_specs["bend_count"] == 4
    assert result.extracted_specs["hole_count"] == 6
    assert result.extracted_specs["surface_finish"] == "Powder coated"


def test_extract_specs_from_searchable_sm1001_layer() -> None:
    result = extract_specs_from_text(
        """
        Part ID: SM-1001
        Category: Bracket
        Material: Mild Steel
        Material Grade: IS 2062 E250
        Thickness: 4.0 mm
        Length: 401 mm
        Width: 330 mm
        Weight: 3.42 kg
        Bend Count: 2
        Hole Count: 16
        Surface Finish: Painted
        """,
        file_name="SM-1001_searchable.pdf",
    )

    assert result.confidence == "High"
    assert result.missing_specs == []
    assert result.extracted_specs == {
        "category": "Bracket",
        "material": "Mild Steel",
        "material_grade": "IS 2062 E250",
        "surface_finish": "Painted",
        "thickness_mm": 4.0,
        "length_mm": 401.0,
        "width_mm": 330.0,
        "weight_kg": 3.42,
        "bend_count": 2,
        "hole_count": 16,
    }


if __name__ == "__main__":
    test_extract_specs_from_manufacturing_drawing_text()
    test_extract_specs_from_searchable_sm1001_layer()
    print("Drawing extractor tests passed")
