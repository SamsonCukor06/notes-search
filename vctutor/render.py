"""Render a unit (a whole section of a note) as images cropped from the original PDF, so
the demo shows the typeset math instead of extracted text."""
from __future__ import annotations

from pathlib import Path

import pymupdf

from . import config


def notes_path(file: str) -> Path:
    return Path(config.load_local_config()["notes_dir"]) / file


def _text_column(page: pymupdf.Page) -> tuple[float, float]:
    """Left and right edges of the text on a page (so figures and boxes aren't cut off)."""
    xs = [b[:4] for b in page.get_text("blocks") if b[4].strip()]
    if not xs:
        return page.rect.x0, page.rect.x1
    return min(b[0] for b in xs), max(b[2] for b in xs)


def render_region(pdf_path: str, page: int, bbox: list[float], dpi: int = 288, pad: float = 8) -> bytes:
    """PNG of one page region: the unit's lines on that page, across the full text column.
    Figures and drawings that overlap the region vertically are included. 288 dpi (4x the
    PDF's 72 points per inch) keeps text sharp on high-resolution screens."""
    with pymupdf.open(pdf_path) as pdf:
        pg = pdf[page - 1]
        left, right = _text_column(pg)
        x0, y0, x1, y1 = min(left, bbox[0]), bbox[1], max(right, bbox[2]), bbox[3]
        for d in pg.get_drawings():  # extend to boxes/figures that start inside the region
            r = d["rect"]
            if r.y0 < y1 and r.y1 > y0 and r.height < pg.rect.height * 0.9:
                x0, x1 = min(x0, r.x0), max(x1, r.x1)
        clip = pymupdf.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & pg.rect
        return pg.get_pixmap(clip=clip, dpi=dpi).tobytes("png")


def unit_pdf(unit: dict) -> str:
    """Where a unit's PDF is (older indexes stored only the path inside the notes folder)."""
    return unit.get("pdf_path") or str(notes_path(unit["file"]))


def render_unit(unit: dict, dpi: int = 288) -> list[bytes]:
    return [render_region(unit_pdf(unit), r["page"], r["bbox"], dpi) for r in unit["regions"]]
