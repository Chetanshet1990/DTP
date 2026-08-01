from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest


def test_upload_drawing_view_persists_across_reruns() -> None:
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run(timeout=60)
    assert not app.exception
    assert app.radio[0].label == "Workspace view"
    assert app.radio[0].value == "Portfolio"

    app.radio[0].set_value("Upload Drawing").run(timeout=60)
    assert not app.exception
    assert app.radio[0].value == "Upload Drawing"
    assert any(header.value == "Upload Drawing" for header in app.subheader)
    initial_uploader_key = app.get("file_uploader")[0].proto.id
    assert "SM-1001" in initial_uploader_key

    app.selectbox[0].set_value("SM-1002").run(timeout=60)
    assert not app.exception
    sm1002_uploader_key = app.get("file_uploader")[0].proto.id
    assert "SM-1002" in sm1002_uploader_key
    assert sm1002_uploader_key != initial_uploader_key

    app.selectbox[0].set_value("SM-1001").run(timeout=60)
    assert not app.exception
    returned_uploader_key = app.get("file_uploader")[0].proto.id
    assert "SM-1001" in returned_uploader_key
    assert returned_uploader_key != initial_uploader_key

    app.run(timeout=60)
    assert not app.exception
    assert app.radio[0].value == "Upload Drawing"


if __name__ == "__main__":
    test_upload_drawing_view_persists_across_reruns()
    print("App navigation tests passed")
