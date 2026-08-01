from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.drawing_review import (
    build_vertical_review_table,
    reviewed_specs_from_vertical_table,
)


FIELDS = [
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
]


def test_vertical_review_table_round_trip() -> None:
    candidate = pd.Series(
        {
            "category": "Bracket",
            "material": "Mild Steel",
            "material_grade": "IS 2062 E250",
            "thickness_mm": 4.0,
            "length_mm": 401.0,
            "width_mm": 330.0,
            "weight_kg": 3.42,
            "bend_count": 2.0,
            "hole_count": 16.0,
            "surface_finish": "Painted",
        }
    )

    table = build_vertical_review_table(candidate, FIELDS)
    assert table.columns.tolist() == ["Parameter", "Reviewed value"]
    assert len(table) == 10
    assert table.loc[table["Parameter"].eq("Bend count"), "Reviewed value"].iloc[0] == "2"

    table.loc[table["Parameter"].eq("Hole count"), "Reviewed value"] = "18"
    reviewed = reviewed_specs_from_vertical_table(table, FIELDS, normalize=True)
    assert reviewed["thickness_mm"] == 4.0
    assert reviewed["bend_count"] == 2
    assert reviewed["hole_count"] == 18
    assert reviewed["surface_finish"] == "Painted"


if __name__ == "__main__":
    test_vertical_review_table_round_trip()
    print("Drawing review tests passed")
