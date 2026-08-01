from __future__ import annotations

import pandas as pd


DRAWING_SPEC_LABELS = {
    "category": "Category",
    "material": "Material",
    "material_grade": "Material grade",
    "thickness_mm": "Thickness (mm)",
    "length_mm": "Overall length (mm)",
    "width_mm": "Overall width (mm)",
    "weight_kg": "Weight (kg)",
    "bend_count": "Bend count",
    "hole_count": "Hole count",
    "surface_finish": "Surface finish",
}

FLOAT_DRAWING_FIELDS = {"thickness_mm", "length_mm", "width_mm", "weight_kg"}
COUNT_DRAWING_FIELDS = {"bend_count", "hole_count"}


def _display_value(field: str, value: object) -> str:
    if pd.isna(value):
        return ""
    if field in COUNT_DRAWING_FIELDS:
        numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if not pd.isna(numeric_value) and float(numeric_value).is_integer():
            return str(int(numeric_value))
    return str(value)


def build_vertical_review_table(
    candidate: pd.Series,
    fields: list[str],
) -> pd.DataFrame:
    """Transpose one candidate part into editable Parameter/Value rows."""
    return pd.DataFrame(
        {
            "Parameter": [DRAWING_SPEC_LABELS.get(field, field) for field in fields],
            "Reviewed value": [_display_value(field, candidate.get(field)) for field in fields],
        }
    )


def reviewed_specs_from_vertical_table(
    reviewed_table: pd.DataFrame,
    fields: list[str],
    normalize: bool = False,
) -> dict[str, object]:
    """Convert the vertical editor result back to the engineering schema."""
    label_to_field = {
        DRAWING_SPEC_LABELS.get(field, field): field
        for field in fields
    }
    specs = {}
    for _, row in reviewed_table.iterrows():
        field = label_to_field.get(str(row["Parameter"]))
        if field:
            specs[field] = row["Reviewed value"]

    missing_rows = [field for field in fields if field not in specs]
    if missing_rows:
        raise ValueError("Review table is missing fields: " + ", ".join(missing_rows))
    if not normalize:
        return specs

    normalized = {}
    for field, value in specs.items():
        if field in FLOAT_DRAWING_FIELDS:
            normalized[field] = float(value)
        elif field in COUNT_DRAWING_FIELDS:
            normalized[field] = int(float(value))
        else:
            normalized[field] = str(value).strip()
    return normalized
