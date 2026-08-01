from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_drawing_ingestion_demo import (
    DRAWING_TECHNICAL_FIELDS,
    prepare_parts_for_drawing_ingestion,
)


def test_prepare_selected_parts_preserves_commercial_data() -> None:
    source = pd.read_csv(PROJECT_ROOT / "data/sample_parts.csv").head(3)
    original_erp_prices = source.set_index("part_id")["erp_price"].copy()

    with TemporaryDirectory(prefix="dtp_demo_prepare_") as temporary_directory:
        active_path = Path(temporary_directory) / "active_parts_master.csv"
        source.to_csv(active_path, index=False)
        prepared = prepare_parts_for_drawing_ingestion(
            active_path,
            ["SM-1001", "SM-1002"],
        )
        result = pd.read_csv(active_path)

    assert prepared["part_id"].tolist() == ["SM-1001", "SM-1002"]
    reset_rows = result[result["part_id"].isin(["SM-1001", "SM-1002"])]
    assert reset_rows[DRAWING_TECHNICAL_FIELDS].isna().all().all()
    assert set(reset_rows["engineering_status"]) == {"Awaiting drawing"}
    assert set(reset_rows["prediction_status"]) == {"Blocked"}
    assert result.set_index("part_id")["erp_price"].equals(original_erp_prices)
    assert result.loc[result["part_id"].eq("SM-1003"), "material_grade"].notna().all()


if __name__ == "__main__":
    test_prepare_selected_parts_preserves_commercial_data()
    print("Drawing demonstration preparation tests passed")
