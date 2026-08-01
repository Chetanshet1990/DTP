from __future__ import annotations

import base64
import html
from io import BytesIO

from PIL import Image
import pypdfium2 as pdfium


def load_raster_image(content: bytes) -> Image.Image:
    """Load uploaded raster-image bytes into a detached RGB image."""
    with Image.open(BytesIO(content)) as image:
        return image.convert("RGB").copy()


def build_zoomable_preview_html(
    image: Image.Image,
    caption: str,
    default_zoom: float = 2.0,
) -> str:
    """Build an isolated hover-to-zoom drawing viewer for components.v1."""
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded_image = base64.b64encode(buffer.getvalue()).decode("ascii")
    safe_caption = html.escape(caption)
    safe_zoom = default_zoom if default_zoom in {1.5, 2.0, 3.0} else 2.0
    template = """
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
      .hint { color: #4b5563; font-size: 13px; }
      .zoom-buttons { display: flex; gap: 6px; }
      .zoom-button { border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; color: #1f2937; padding: 4px 9px; cursor: pointer; }
      .zoom-button.active { background: #0f766e; border-color: #0f766e; color: #fff; }
      .viewport { height: 620px; overflow: hidden; border: 1px solid #d1d5db; border-radius: 8px; background: #f8fafc; cursor: crosshair; }
      .drawing { width: 100%; height: 100%; object-fit: contain; transform: scale(1); transform-origin: 50% 50%; transition: transform 90ms ease-out; will-change: transform; }
      .caption { margin-top: 7px; color: #4b5563; font-size: 12px; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
    <div class="toolbar">
      <span class="hint">Move the cursor over the drawing to magnify</span>
      <div class="zoom-buttons">
        <button class="zoom-button" data-zoom="1.5">1.5×</button>
        <button class="zoom-button" data-zoom="2">2×</button>
        <button class="zoom-button" data-zoom="3">3×</button>
      </div>
    </div>
    <div class="viewport" id="drawing-viewport">
      <img class="drawing" id="drawing-image" src="data:image/png;base64,__IMAGE_DATA__" alt="Drawing preview">
    </div>
    <div class="caption">__CAPTION__</div>
    <script>
      const viewport = document.getElementById("drawing-viewport");
      const drawing = document.getElementById("drawing-image");
      const buttons = Array.from(document.querySelectorAll(".zoom-button"));
      let zoom = __DEFAULT_ZOOM__;
      let hovering = false;

      function updateButtons() {
        buttons.forEach(button => {
          button.classList.toggle("active", Number(button.dataset.zoom) === zoom);
        });
      }
      function applyZoom() {
        drawing.style.transform = hovering ? `scale(${zoom})` : "scale(1)";
      }
      buttons.forEach(button => {
        button.addEventListener("click", () => {
          zoom = Number(button.dataset.zoom);
          updateButtons();
          applyZoom();
        });
      });
      viewport.addEventListener("mouseenter", () => {
        hovering = true;
        applyZoom();
      });
      viewport.addEventListener("mousemove", event => {
        const bounds = viewport.getBoundingClientRect();
        const x = Math.max(0, Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100));
        const y = Math.max(0, Math.min(100, ((event.clientY - bounds.top) / bounds.height) * 100));
        drawing.style.transformOrigin = `${x}% ${y}%`;
      });
      viewport.addEventListener("mouseleave", () => {
        hovering = false;
        drawing.style.transform = "scale(1)";
        drawing.style.transformOrigin = "50% 50%";
      });
      updateButtons();
    </script>
    """
    return (
        template.replace("__IMAGE_DATA__", encoded_image)
        .replace("__CAPTION__", safe_caption)
        .replace("__DEFAULT_ZOOM__", str(safe_zoom))
    )


def pdf_page_count(content: bytes) -> int:
    """Return the number of pages in an uploaded PDF."""
    document = pdfium.PdfDocument(content)
    try:
        return len(document)
    finally:
        document.close()


def render_pdf_page(content: bytes, page_number: int = 1, scale: float = 1.5) -> Image.Image:
    """Render one PDF page to a detached PIL image for Streamlit preview."""
    document = pdfium.PdfDocument(content)
    try:
        if page_number < 1 or page_number > len(document):
            raise ValueError(f"PDF page must be between 1 and {len(document)}.")
        page = document[page_number - 1]
        try:
            bitmap = page.render(scale=scale)
            try:
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                buffer.seek(0)
                return Image.open(buffer).copy()
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()
