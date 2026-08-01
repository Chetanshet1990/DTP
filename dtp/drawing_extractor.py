from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# REVIEW EXPLANATION:
# This module is the Review 3 drawing-ingestion layer. It turns text extracted
# from manufacturing drawings into the structured fields required by the Cost
# Digital Twin and ML fair-price model.


@dataclass(frozen=True)
class DrawingSpecResult:
    """Structured specifications extracted from one drawing."""

    file_name: str
    extracted_specs: dict[str, object]
    confidence: str
    missing_specs: list[str]
    evidence: dict[str, str]


SPEC_FIELDS = [
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

CATEGORY_PATTERNS = {
    "Bracket": r"\b(?:category\s*[:=]?\s*)?(?:mounting\s+|control\s+)?bracket\b",
    "Mounting plate": r"\b(?:category\s*[:=]?\s*)?mounting\s+plate\b",
    "Cover / panel": r"\b(?:category\s*[:=]?\s*)?(?:cover|panel)\b",
    "Fabricated assembly": r"\b(?:category\s*[:=]?\s*)?(?:fabricated\s+assembly|welded\s+support)\b",
}

MATERIAL_TYPE_PATTERNS = {
    "Mild Steel": r"\bmild\s+steel\b",
    "Stainless Steel": r"\bstainless\s+steel\b",
    "CRCA Steel": r"\bcrca\s+steel\b",
    "Galvanized Steel": r"\bgalvani[sz]ed\s+steel\b",
}

MATERIAL_PATTERNS = [
    r"\bIS\s*2062\s*E\s*250\b",
    r"\bIS\s*2062\s*E\s*350\b",
    r"\bCRCA\s*IS\s*513\b",
    r"\bGI\s*G90\b",
    r"\bSS\s*304\b",
]

FINISH_PATTERNS = {
    "Powder coated": r"powder\s*coat(?:ed|ing)?",
    "Zinc plated": r"zinc\s*plat(?:ed|ing)",
    "Painted": r"\bpaint(?:ed|ing)?\b",
    "Passivated": r"\bpassivat(?:ed|ion)?\b",
}


def _first_float(pattern: str, text: str) -> tuple[float | None, str | None]:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None, None
    return float(match.group(1)), match.group(0)


def extract_specs_from_text(text: str, file_name: str = "uploaded_drawing") -> DrawingSpecResult:
    """Extract key manufacturing specs from OCR/PDF text."""
    normalized = re.sub(r"\s+", " ", text).strip()
    specs: dict[str, object] = {}
    evidence: dict[str, str] = {}

    for category, pattern in CATEGORY_PATTERNS.items():
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            specs["category"] = category
            evidence["category"] = match.group(0)
            break

    for material, pattern in MATERIAL_TYPE_PATTERNS.items():
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            specs["material"] = material
            evidence["material"] = match.group(0)
            break

    for pattern in MATERIAL_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            specs["material_grade"] = re.sub(r"\s+", " ", match.group(0).upper()).replace("SS 304", "SS304")
            evidence["material_grade"] = match.group(0)
            break

    if "material" not in specs and "material_grade" in specs:
        grade = str(specs["material_grade"])
        if grade.startswith("IS 2062"):
            specs["material"] = "Mild Steel"
        elif grade.startswith("CRCA"):
            specs["material"] = "CRCA Steel"
        elif grade.startswith("GI"):
            specs["material"] = "Galvanized Steel"
        elif grade.startswith("SS"):
            specs["material"] = "Stainless Steel"
        if "material" in specs:
            evidence["material"] = f"Derived from {grade}"

    for finish, pattern in FINISH_PATTERNS.items():
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            specs["surface_finish"] = finish
            evidence["surface_finish"] = match.group(0)
            break

    dimension_patterns = {
        "thickness_mm": r"(?:thk|thickness|t)(?:\s*\(mm\))?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)(?:\s*mm)?",
        "length_mm": r"(?:overall\s+)?(?:length|len|l)(?:\s*\(mm\))?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)(?:\s*mm)?",
        "width_mm": r"(?:overall\s+)?(?:width|wid|w)(?:\s*\(mm\))?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)(?:\s*mm)?",
        "weight_kg": r"(?:weight|mass|wt)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:kg|kgs|kilogram)",
    }
    for field, pattern in dimension_patterns.items():
        value, source = _first_float(pattern, normalized)
        if value is not None:
            specs[field] = value
            evidence[field] = source or ""

    bend_count, bend_source = _first_float(r"(?:bends?|bend\s*count)\s*[:=]?\s*([0-9]+)", normalized)
    if bend_count is not None:
        specs["bend_count"] = int(bend_count)
        evidence["bend_count"] = bend_source or ""

    hole_count, hole_source = _first_float(r"(?:holes?|hole\s*count|(?:[0-9]+)\s*x\s*dia)\s*[:=]?\s*([0-9]+)", normalized)
    if hole_count is not None:
        specs["hole_count"] = int(hole_count)
        evidence["hole_count"] = hole_source or ""
    else:
        hole_callouts = re.findall(r"\b([0-9]+)\s*x\s*(?:dia|ø|diameter)", normalized, flags=re.IGNORECASE)
        if hole_callouts:
            specs["hole_count"] = sum(int(value) for value in hole_callouts)
            evidence["hole_count"] = ", ".join(hole_callouts)

    missing = [field for field in SPEC_FIELDS if field not in specs]
    if not missing:
        confidence = "High"
    elif len(missing) <= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return DrawingSpecResult(
        file_name=file_name,
        extracted_specs=specs,
        confidence=confidence,
        missing_specs=missing,
        evidence=evidence,
    )


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from a PDF drawing when pypdf is available."""
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - optional dependency.
        raise RuntimeError("Install pypdf to extract text from PDF drawings.") from exc

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_specs_from_file(path: Path) -> DrawingSpecResult:
    """Extract drawing specs from text-like drawings and text-based PDFs."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = extract_text_from_pdf(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return extract_specs_from_text(text, file_name=path.name)


def drawing_results_to_frame(results: list[DrawingSpecResult]) -> pd.DataFrame:
    """Convert drawing extraction results into a dashboard-ready table."""
    rows = []
    for result in results:
        row = {
            "file_name": result.file_name,
            "confidence": result.confidence,
            "missing_specs": ", ".join(result.missing_specs),
        }
        row.update(result.extracted_specs)
        rows.append(row)
    return pd.DataFrame(rows)
