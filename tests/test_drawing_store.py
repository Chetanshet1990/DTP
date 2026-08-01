from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.drawing_store import store_committed_drawing


def test_committed_drawing_is_stored_in_part_directory_with_audit_metadata() -> None:
    content = b"%PDF-1.4\nphase-1-test\n%%EOF\n"
    commit_time = datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc)

    with TemporaryDirectory(prefix="dtp_drawing_store_") as temporary_directory:
        root = Path(temporary_directory)
        stored = store_committed_drawing(
            content=content,
            original_file_name="SM-1001.pdf",
            part_id="SM-1001",
            drawings_directory=root / "data/drawings",
            project_root=root,
            committed_at=commit_time,
        )

        assert stored.absolute_path.exists()
        assert stored.absolute_path.read_bytes() == content
        assert stored.relative_path == (
            "data/drawings/committed/SM-1001/SM-1001_20260801T103000000000Z.pdf"
        )
        assert len(stored.sha256) == 64
        assert stored.committed_at_utc == "2026-08-01T10:30:00+00:00"
        assert not list(stored.absolute_path.parent.glob("*.tmp"))


if __name__ == "__main__":
    test_committed_drawing_is_stored_in_part_directory_with_audit_metadata()
    print("Drawing store tests passed")
