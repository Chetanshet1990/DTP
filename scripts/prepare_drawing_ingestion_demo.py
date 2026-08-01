from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVE_MASTER = PROJECT_ROOT / "data/processed/active_parts_master.csv"

DRAWING_TECHNICAL_FIELDS = [
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

DRAWING_METADATA_FIELDS = [
    "drawing_source_file",
    "drawing_stored_path",
    "drawing_sha256",
    "drawing_committed_at_utc",
]


def prepare_parts_for_drawing_ingestion(
    active_master_path: Path,
    part_ids: list[str],
) -> pd.DataFrame:
    """Reset selected parts to Awaiting drawing without deleting stored files."""
    if not active_master_path.exists():
        raise FileNotFoundError(f"Active part master not found: {active_master_path}")
    if not part_ids:
        raise ValueError("Provide at least one part ID.")

    parts = pd.read_csv(active_master_path)
    requested_ids = {str(part_id).strip() for part_id in part_ids if str(part_id).strip()}
    available_ids = set(parts["part_id"].astype(str))
    missing_ids = sorted(requested_ids - available_ids)
    if missing_ids:
        raise ValueError("Part IDs not found: " + ", ".join(missing_ids))

    selected = parts["part_id"].astype(str).isin(requested_ids)
    for field in DRAWING_TECHNICAL_FIELDS + DRAWING_METADATA_FIELDS:
        if field not in parts.columns:
            parts[field] = pd.NA
        parts.loc[selected, field] = pd.NA

    parts.loc[selected, "engineering_data_source"] = "Awaiting drawing"
    parts.loc[selected, "drawing_extraction_confidence"] = "Blocked"
    parts.loc[selected, "engineering_status"] = "Awaiting drawing"
    parts.loc[selected, "prediction_status"] = "Blocked"

    temporary_path = active_master_path.with_suffix(".demo.tmp")
    parts.to_csv(temporary_path, index=False)
    temporary_path.replace(active_master_path)

    return parts.loc[
        selected,
        ["part_id", "engineering_status", "prediction_status"],
    ].sort_values("part_id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare selected parts for the drawing-ingestion UI demonstration."
    )
    parser.add_argument(
        "part_ids",
        nargs="+",
        help="Part IDs to reset, for example SM-1001 SM-1002.",
    )
    parser.add_argument(
        "--active-master",
        type=Path,
        default=DEFAULT_ACTIVE_MASTER,
        help="Path to the persistent active part master CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared = prepare_parts_for_drawing_ingestion(
        active_master_path=args.active_master,
        part_ids=args.part_ids,
    )
    print("Drawing-ingestion demonstration state prepared:")
    print(prepared.to_string(index=False))
    print("Stored drawing files were preserved.")
    print("Restart Streamlit to clear existing browser/session widget state.")


if __name__ == "__main__":
    main()
