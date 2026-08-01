from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re


ALLOWED_DRAWING_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".dxf", ".dwg"}


@dataclass(frozen=True)
class StoredDrawing:
    absolute_path: Path
    relative_path: str
    sha256: str
    committed_at_utc: str


def _safe_part_id(part_id: str) -> str:
    safe_value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(part_id)).strip("._")
    if not safe_value:
        raise ValueError("Part ID cannot be converted to a safe storage directory name.")
    return safe_value


def store_committed_drawing(
    content: bytes,
    original_file_name: str,
    part_id: str,
    drawings_directory: Path,
    project_root: Path,
    committed_at: datetime | None = None,
) -> StoredDrawing:
    """Atomically persist one drawing after its reviewed data passes validation."""
    if not content:
        raise ValueError("Uploaded drawing is empty.")

    suffix = Path(original_file_name).suffix.lower()
    if suffix not in ALLOWED_DRAWING_SUFFIXES:
        raise ValueError(f"Unsupported drawing file type: {suffix or 'missing extension'}")

    safe_part_id = _safe_part_id(part_id)
    commit_time = committed_at or datetime.now(timezone.utc)
    if commit_time.tzinfo is None:
        commit_time = commit_time.replace(tzinfo=timezone.utc)
    commit_time = commit_time.astimezone(timezone.utc)
    timestamp = commit_time.strftime("%Y%m%dT%H%M%S%fZ")

    target_directory = drawings_directory / "committed" / safe_part_id
    target_directory.mkdir(parents=True, exist_ok=True)
    target_path = target_directory / f"{safe_part_id}_{timestamp}{suffix}"
    temporary_path = target_path.with_suffix(target_path.suffix + ".tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(target_path)

    return StoredDrawing(
        absolute_path=target_path,
        relative_path=target_path.relative_to(project_root).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        committed_at_utc=commit_time.isoformat(),
    )
