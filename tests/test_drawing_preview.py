from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dtp.drawing_preview import (
    build_zoomable_preview_html,
    pdf_page_count,
    render_pdf_page,
)


def _sample_pdf() -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(400, 300))
    pdf.drawString(40, 250, "SM-1001 drawing preview test")
    pdf.showPage()
    pdf.drawString(40, 250, "Page 2")
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def test_pdf_preview_renders_requested_page() -> None:
    content = _sample_pdf()
    assert pdf_page_count(content) == 2

    preview = render_pdf_page(content, page_number=1, scale=1.5)
    assert preview.width == 600
    assert preview.height == 450

    viewer_html = build_zoomable_preview_html(preview, "SM-1001 <drawing>")
    assert "data:image/png;base64," in viewer_html
    assert 'addEventListener("mousemove"' in viewer_html
    assert "1.5×" in viewer_html
    assert "2×" in viewer_html
    assert "3×" in viewer_html
    assert "SM-1001 &lt;drawing&gt;" in viewer_html


if __name__ == "__main__":
    test_pdf_preview_renders_requested_page()
    print("Drawing preview tests passed")
