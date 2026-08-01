from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


SM1001_SPECIFICATION_TEXT = [
    "Part ID: SM-1001",
    "Category: Bracket",
    "Material: Mild Steel",
    "Material Grade: IS 2062 E250",
    "Thickness: 4.0 mm",
    "Length: 401 mm",
    "Width: 330 mm",
    "Weight: 3.42 kg",
    "Bend Count: 2",
    "Hole Count: 16",
    "Surface Finish: Painted",
]


def _page_size(source: Path) -> tuple[float, float]:
    result = subprocess.run(
        ["pdfinfo", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Page size:\s*([0-9.]+)\s+x\s+([0-9.]+)\s+pts", result.stdout)
    if not match:
        raise ValueError("Could not determine PDF page size from pdfinfo output.")
    return float(match.group(1)), float(match.group(2))


def generate_searchable_drawing(source: Path, output: Path) -> None:
    """Preserve the drawing image and add a searchable specification text layer."""
    width, height = _page_size(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="dtp_drawing_") as temporary_directory:
        image_prefix = Path(temporary_directory) / "drawing"
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-f",
                "1",
                "-singlefile",
                "-r",
                "150",
                str(source),
                str(image_prefix),
            ],
            check=True,
        )
        page_image = image_prefix.with_suffix(".png")

        pdf = canvas.Canvas(str(output), pagesize=(width, height), pageCompression=1)
        pdf.setTitle("SM-1001 Searchable Manufacturing Drawing")
        pdf.setSubject("Sheet-metal drawing with machine-readable specifications")
        pdf.drawImage(
            ImageReader(str(page_image)),
            0,
            0,
            width=width,
            height=height,
            preserveAspectRatio=False,
        )

        # PDF text rendering mode 3 is invisible but remains searchable and can be
        # extracted by pypdf. The visible drawing is unchanged.
        text_layer = pdf.beginText(36, height - 36)
        text_layer.setFont("Helvetica", 9)
        text_layer.setTextRenderMode(3)
        for line in SM1001_SPECIFICATION_TEXT:
            text_layer.textLine(line)
        pdf.drawText(text_layer)
        pdf.showPage()
        pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a searchable specification layer to an image-based drawing PDF."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    generate_searchable_drawing(args.input, args.output)


if __name__ == "__main__":
    main()
