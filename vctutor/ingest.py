"""Read the PDF notes, clean up the math, group lines into whole sections ("units"),
and split the text into chunks for search (data/<chunking>/chunks.jsonl, data/units.jsonl).

Each PDF file name starts with its section number, e.g.
"13.2.2 - Line Integrals (Lecture 34).pdf" -> doc_id "13.2.2", section "13.2", chapter "13".
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from . import config

# LaTeX's big-operator font (CMEX) has no Unicode map, so PDF readers return plain
# letters: a display integral comes out as "Z", a contour integral as "I", a sum as "X".
# Map them back to the real symbols.
CMEX_MAP = {
    "Z": "∫", "R": "∫",  # \int (display, text)
    "I": "∮", "H": "∮",  # \oint
    "X": "∑", "P": "∑",  # \sum
    "Y": "∏", "Q": "∏",  # \prod
    "p": "√", "q": "√", "r": "√", "s": "√",  # \sqrt signs
}
# Big delimiters in CMEX use control-character codes.
CMEX_OPEN = set("\x00\x02\x04\x06\x08\x0a\x0c\x0e\x10\x12\x14\x16\x18\x1a\x1c\x1e\x20\x22\x24\x26\x28\x2a\x2c\x2e")
CMEX_CLOSE = set("\x01\x03\x05\x07\x09\x0b\x0d\x0f\x11\x13\x15\x17\x19\x1b\x1d\x1f\x21\x23\x25\x27\x29\x2b\x2d\x2f")


def _fix_span(text: str, font: str) -> str:
    if "CMEX" not in font.upper():
        return text
    out = []
    for ch in text:
        if ch in CMEX_MAP:
            out.append(CMEX_MAP[ch])
        elif ch in CMEX_OPEN:
            out.append("(")
        elif ch in CMEX_CLOSE:
            out.append(")")
        # anything else in CMEX is a stretchy piece of a bracket or brace: drop it
    return "".join(out)


def _script_marker(span: dict, base_y: float, base_size: float) -> str:
    """'^' for a raised smaller span (exponent), '_' for a lowered one (subscript)."""
    if span["size"] > 0.85 * base_size:
        return ""
    y = span["origin"][1]
    if y < base_y - 0.15 * base_size:
        return "^"
    if y > base_y + 0.08 * base_size:
        return "_"
    return ""


def _is_bold(span: dict) -> bool:
    f = span["font"]
    return bool(span["flags"] & 16) or "BX" in f or "Bold" in f or "-Bd" in f


def _is_heading(spans: list[dict], text: str) -> bool:
    """A short line set entirely in bold: '1. Introduction to Line Integrals',
    'Definition / Core Concept: Work', 'Example: Bounded Volume'."""
    text_spans = [s for s in spans if "CMEX" not in s["font"].upper()]
    return (
        bool(text_spans)
        and all(_is_bold(s) for s in text_spans)
        and len(text) <= 90
        and any(ch.isalpha() for ch in text)
    )


def _frac(m: re.Match) -> str:
    num, den = (g.strip("{}") for g in m.groups())
    wrap = lambda t: t if len(t) == 1 or t.isalnum() else f"({t})"
    return f"{wrap(num)}/{wrap(den)}"


def clean_line(text: str) -> str:
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")  # ligatures
    # a small raised piece followed by a small lowered piece, with no base before it,
    # is an inline fraction: "^1 _5" -> "1/5", "^{x+1} _{2}" -> "(x+1)/2"
    text = re.sub(r"(?<![\w)\]}])\^(\{[^{}]*\}|\S)[ \t]*_(\{[^{}]*\}|\S)", _frac, text)
    # runs of stretchy-bracket pieces from tall matrices and fractions are noise
    text = re.sub(r"(?:\(\s*){3,}", "( ", text)
    text = re.sub(r"(?:\)\s*){3,}", ") ", text)
    return text.strip()


@dataclass
class Line:
    page: int  # 1-based page number
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points
    level: int  # 0 = text, 1 = bold label ("Step 1:", "Takeaway:"), 2 = section heading


SECTION_HEADING_RATIO = 1.08  # section headings are set at least this much bigger than body text


def body_size(pdf: pymupdf.Document) -> float:
    """The most common font size in the document (weighted by characters)."""
    sizes: dict[float, int] = {}
    for page in pdf:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for s in line["spans"]:
                    if s["text"].strip() and "CMEX" not in s["font"].upper():
                        k = round(s["size"], 1)
                        sizes[k] = sizes.get(k, 0) + len(s["text"])
    return max(sizes, key=sizes.get) if sizes else 10.0


def page_lines(page: pymupdf.Page, page_no: int, body: float) -> list[Line]:
    """Lines of one page, with LaTeX big operators turned back into symbols,
    exponents/subscripts written as x^2 and x_0, and heading levels marked."""
    out = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            # the line's normal text size: the longest non-CMEX span (big brackets don't count)
            text_spans = [s for s in spans if "CMEX" not in s["font"].upper()] or spans
            base = max(text_spans, key=lambda s: len(s["text"].strip()))
            base_y, base_size = base["origin"][1], base["size"]
            parts, prev_x1 = [], None
            for span in spans:
                t = _fix_span(span["text"], span["font"])
                if not t:
                    continue
                x0, x1 = span["bbox"][0], span["bbox"][2]
                # add a space when there's a visible gap between spans (font switches)
                if prev_x1 is not None and x0 - prev_x1 > 0.15 * span["size"] and not t.startswith(" "):
                    parts.append(" ")
                mark = _script_marker(span, base_y, base_size)
                if mark:
                    t = t.strip()
                    t = mark + (t if len(t) == 1 else "{" + t + "}")
                parts.append(t)
                prev_x1 = x1
            text = clean_line("".join(parts))
            if not text:
                continue
            if text.isdigit() and line["bbox"][1] > 0.9 * page.rect.height:
                continue  # page number in the footer
            level = 0
            real_text = [s for s in spans if "CMEX" not in s["font"].upper()]
            letters = sum(ch.isalpha() and ch.isascii() for ch in text)
            if real_text and letters >= 3:  # a line of display math is never a heading
                size = max(s["size"] for s in real_text)
                if _is_heading(spans, text):
                    level = 2 if size >= SECTION_HEADING_RATIO * body else 1
                elif len(text) <= 90 and size >= 1.3 * body:
                    level = 2  # large title set in a regular weight
            out.append(Line(page_no, text, tuple(line["bbox"]), level))
    return out


def drop_running_headers(lines: list[Line], page_height: float, margin: float = 0.08) -> list[Line]:
    """Remove running headers and footers: a line in the top or bottom margin whose text
    shows up on two or more pages (like 'Vector Calculus: Line Integrals  Lecture 36')."""
    def in_margin(ln: Line) -> bool:
        return ln.bbox[1] > (1 - margin) * page_height or ln.bbox[3] < margin * page_height

    pages_with: dict[str, set[int]] = {}
    for ln in lines:
        if in_margin(ln):
            pages_with.setdefault(ln.text, set()).add(ln.page)
    repeated = {t for t, pgs in pages_with.items() if len(pgs) >= 2}
    return [ln for ln in lines if not (in_margin(ln) and ln.text in repeated)]


def page_text(page: pymupdf.Page) -> str:
    """Plain text of one page (used for quick checks)."""
    return "\n".join(l.text for l in page_lines(page, 1, body_size(page.parent)))


@dataclass
class Doc:
    doc_id: str
    title: str
    chapter: str
    sections: list[str]
    kind: str  # "lecture", "slide-deck notes", "review" or "notes"
    file: str
    lines: list[Line] = field(default_factory=list)
    n_pages: int = 0
    pdf_path: str = ""  # absolute path, so pages can be rendered later


NAME_RE = re.compile(r"^(?P<num>[\d.a-z]+(?:\s*&\s*[\d.a-z]+)*)\.?\s*-\s*(?P<title>.+)$")
SECTION_NUM_RE = re.compile(r"\b(\d+(?:\.\d+)+[a-z]?)\b")
DATE_RE = re.compile(r"\s*[-–]?\s*\(?\d{4}-\d{2}-\d{2}\)?\s*$")


def parse_name(path: Path) -> tuple[str, str, str, list[str], str]:
    """File name -> (doc_id, title, chapter, sections, kind).

    '13.2.2 - Line Integrals (Lecture 34).pdf' -> '13.2.2', 'Line Integrals (Lecture 34)', '13', ['13.2']
    'Topic 1.3 - First-Order Linear Equations - 2026-10-22.pdf' -> '1.3', 'First-Order Linear Equations'
    'Week 4 notes.pdf' (no section number) -> 'week-4-notes', 'Week 4 notes', '', []"""
    stem = DATE_RE.sub("", path.stem).strip()
    kind = "notes"
    if re.search(r"\(.*Lecture \d+", stem):
        kind = "lecture"
    if "Slide Deck" in stem or "Slides" in stem:
        kind = "slide-deck notes"
    title = re.sub(r"\s*\((Lecture|Slide|Slides)[^)]*\)\s*$", "", stem).strip()  # drop "(Lecture 34)" etc.
    lec = re.search(r"Lecture (\d+)", stem)
    m = NAME_RE.match(title)
    if m:  # starts with a section number
        nums = [n.strip().rstrip(".") for n in m.group("num").split("&")]
        title = m.group("title").strip()
        doc_id = " & ".join(nums)
        sections = sorted({".".join(n.split(".")[:2]) for n in nums})
        chapter = nums[0].split(".")[0]
    elif re.search(r"review", stem, re.I) and lec:  # e.g. "Exam 1 Review (Lecture 14)"
        doc_id, sections, chapter, kind = f"review-L{lec.group(1)}", ["review"], "review", "review"
    else:
        num = SECTION_NUM_RE.search(title.split(" - ")[0])  # e.g. "Topic 1.3 - ..."
        if num and " - " in title:
            doc_id = num.group(1)
            title = title.split(" - ", 1)[1].strip()
            sections, chapter = [".".join(doc_id.split(".")[:2])], doc_id.split(".")[0]
        else:
            doc_id, sections, chapter = re.sub(r"\W+", "-", title).strip("-").lower() or "notes", [], ""
    if lec and kind != "review":
        title = f"{title} (Lecture {lec.group(1)})"
    return doc_id, title, chapter, sections, kind


def find_pdfs(cfg: dict) -> tuple[list[Path], list[dict]]:
    root = Path(cfg["notes_dir"])
    if not root.is_dir():
        raise SystemExit(f"notes_dir not found: {root}")
    keep, skipped = [], []
    for p in sorted(root.rglob("*.pdf")):
        rel = p.relative_to(root)
        if any(part in cfg["exclude_dirs"] for part in rel.parts[:-1]):
            skipped.append({"file": str(rel), "reason": "excluded folder"})
        elif p.name in cfg["exclude_files"]:
            skipped.append({"file": str(rel), "reason": "excluded file"})
        else:
            keep.append(p)
    return keep, skipped


def read_pdf(p: Path, root: Path) -> Doc | None:
    """One PDF -> Doc (None if it has no extractable text, e.g. a scan)."""
    doc_id, title, chapter, sections, kind = parse_name(p)
    with pymupdf.open(p) as pdf:
        body = body_size(pdf)
        lines = [ln for i, pg in enumerate(pdf, start=1) for ln in page_lines(pg, i, body)]
        n_pages = len(pdf)
        lines = drop_running_headers(lines, pdf[0].rect.height)
    if sum(len(ln.text) for ln in lines) < 200:
        return None
    try:
        rel = str(p.relative_to(root))
    except ValueError:
        rel = p.name
    return Doc(doc_id, title, chapter, sections, kind, rel, lines, n_pages, str(p.resolve()))


def load_pdfs(paths: list[Path], root: Path, progress=None) -> tuple[list[Doc], list[dict]]:
    docs, skipped, seen = [], [], {}
    for i, p in enumerate(paths, start=1):
        if progress:
            progress(i / max(len(paths), 1), f"Reading {p.name}")
        try:
            doc = read_pdf(p, root)
        except Exception as e:  # a broken or encrypted PDF shouldn't stop the rest
            skipped.append({"file": p.name, "reason": f"couldn't read it ({type(e).__name__})"})
            continue
        if doc is None:
            skipped.append({"file": p.name, "reason": "no text to read (scanned or image-only)"})
            continue
        if doc.doc_id in seen:  # two files with the same section number: keep both apart
            seen[doc.doc_id] += 1
            doc.doc_id = f"{doc.doc_id}~{seen[doc.doc_id]}"
        else:
            seen[doc.doc_id] = 1
        docs.append(doc)
    return docs, skipped


def load_docs(cfg: dict) -> tuple[list[Doc], list[dict]]:
    """The vector calculus notes, as configured in local_config.json."""
    pdfs, skipped = find_pdfs(cfg)
    docs, more = load_pdfs(pdfs, Path(cfg["notes_dir"]))
    return docs, skipped + more


def find_pdfs_in(folder: Path, skip_words: tuple[str, ...] = ("draft",)) -> list[tuple[Path, bool]]:
    """Every PDF under folder, each with a suggested include flag (off if a folder or file
    name contains one of skip_words, like 'Older Drafts')."""
    out = []
    for p in sorted(Path(folder).expanduser().rglob("*.pdf")):
        rel = str(p.relative_to(Path(folder).expanduser())).lower()
        out.append((p, not any(w in rel for w in skip_words)))
    return out


# ---------- units: whole sections of a note, used to give each hit its full context ----------

def build_units(doc: Doc, min_words: int = 60) -> tuple[list[dict], list[int]]:
    """Split a note into units at its section headings (the numbered and "Example"
    headings, set larger than body text). A unit keeps a whole worked example together,
    Step 1 through the end. Returns the units and, for each line, its unit index."""
    groups: list[list[int]] = []
    current: list[int] = []
    for i, ln in enumerate(doc.lines):
        prev_is_heading = bool(current) and doc.lines[current[-1]].level == 2
        if ln.level == 2 and current and not prev_is_heading and _words(doc, current) >= min_words:
            groups.append(current)
            current = []
        current.append(i)
    if current:
        if groups and _words(doc, current) < min_words:
            groups[-1] += current
        else:
            groups.append(current)
    # notes without section headings: one long unit is too much to show at once, so split it by page
    split = []
    for g in groups:
        pages = sorted({doc.lines[i].page for i in g})
        if _words(doc, g) > 700 and len(pages) > 1:
            split += [[i for i in g if doc.lines[i].page == pg] for pg in pages]
        else:
            split.append(g)
    groups = [g for g in split if g]

    units, line_unit = [], [0] * len(doc.lines)
    for n, idxs in enumerate(groups, start=1):
        lines = [doc.lines[i] for i in idxs]
        for i in idxs:
            line_unit[i] = n - 1
        heading = " / ".join(ln.text for ln in lines[:4] if ln.level == 2)[:160]
        if not heading:  # a page-split piece: use its first bold label or first line
            heading = next((ln.text for ln in lines if ln.level >= 1), lines[0].text)[:160]
        regions: dict[int, list[float]] = {}
        for ln in lines:
            r = regions.setdefault(ln.page, [ln.bbox[0], ln.bbox[1], ln.bbox[2], ln.bbox[3]])
            r[0], r[1] = min(r[0], ln.bbox[0]), min(r[1], ln.bbox[1])
            r[2], r[3] = max(r[2], ln.bbox[2]), max(r[3], ln.bbox[3])
        text = "\n".join(ln.text for ln in lines)
        units.append({
            "unit_id": f"{doc.doc_id}:u{n:02d}", "doc_id": doc.doc_id, "title": doc.title,
            "sections": doc.sections, "kind": doc.kind, "file": doc.file, "pdf_path": doc.pdf_path,
            "heading": heading,
            "page_start": lines[0].page, "page_end": lines[-1].page, "n_words": len(text.split()),
            "regions": [{"page": pg, "bbox": [round(v, 1) for v in bb]} for pg, bb in sorted(regions.items())],
            "text": text,
        })
    return units, line_unit


def _words(doc: Doc, idxs: list[int]) -> int:
    return sum(len(doc.lines[i].text.split()) for i in idxs)


def _doc_words(doc: Doc, line_unit: list[int]) -> tuple[list[str], list[int], list[int], list[int]]:
    """All words of a doc with their page, unit index and line index."""
    words, pages, units, line_idx = [], [], [], []
    for i, ln in enumerate(doc.lines):
        w = ln.text.split()
        words += w
        pages += [ln.page] * len(w)
        units += [line_unit[i]] * len(w)
        line_idx += [i] * len(w)
    return words, pages, units, line_idx


def _chunk_record(doc: Doc, units: list[dict], chunk_id: str, pages: list[int], unit_idx: list[int],
                  text: str, unit_offsets: dict[int, int], heading: str | None = None) -> dict:
    main = max(set(unit_idx), key=unit_idx.count)  # the unit holding most of this chunk
    rec = {
        "chunk_id": chunk_id, "doc_id": doc.doc_id, "title": doc.title, "chapter": doc.chapter,
        "sections": doc.sections, "kind": doc.kind, "file": doc.file,
        "page_start": pages[0], "page_end": pages[-1], "text": text,
        "unit_id": units[main]["unit_id"],
        "unit_heading": units[main]["heading"],
        "unit_offset": unit_offsets.get(main, 0),  # where the chunk starts inside its unit (words)
    }
    if heading is not None:
        rec["heading"] = heading
    return rec


def _unit_offsets(unit_idx: list[int], start: int, unit_starts: dict[int, int]) -> dict[int, int]:
    """For each unit a chunk touches, the chunk's first word's position inside that unit."""
    offsets = {}
    for j, u in enumerate(unit_idx):
        offsets.setdefault(u, start + j - unit_starts[u])
    return offsets


def chunk_doc(doc: Doc, units: list[dict], line_unit: list[int], words_per_chunk: int, overlap: int) -> list[dict]:
    """Baseline chunker: fixed windows of words with overlap, keeping page numbers."""
    words, pages, uidx, _ = _doc_words(doc, line_unit)
    unit_starts = {}
    for j, u in enumerate(uidx):
        unit_starts.setdefault(u, j)
    chunks, step, n = [], words_per_chunk - overlap, 0
    for start in range(0, max(len(words) - overlap, 1), step):
        end = min(start + words_per_chunk, len(words))
        if start >= end:
            break
        n += 1
        chunks.append(_chunk_record(doc, units, f"{doc.doc_id}:c{n:02d}", pages[start:end], uidx[start:end],
                                    " ".join(words[start:end]), _unit_offsets(uidx[start:end], start, unit_starts)))
    return chunks


def chunk_doc_sections(doc: Doc, units: list[dict], line_unit: list[int], max_words: int = 300,
                       min_words: int = 40, window: int = 220, overlap: int = 40) -> list[dict]:
    """Section-based chunker: split at every bold heading in the notes (including labels like
    'Step 1:'), so a chunk is one small topic. Tiny pieces merge into the next one; long
    ones are split into overlapping windows that each keep the heading."""
    words, pages, uidx, line_idx = _doc_words(doc, line_unit)
    unit_starts = {}
    for j, u in enumerate(uidx):
        unit_starts.setdefault(u, j)
    # word positions where a heading line starts
    pieces: list[dict] = []
    current = {"heading": "", "start": 0}
    seen_line = -1
    for j, li in enumerate(line_idx):
        if li == seen_line:
            continue
        seen_line = li
        if doc.lines[li].level >= 1:
            if j - current["start"] >= min_words:
                current["end"] = j
                pieces.append(current)
                current = {"heading": "", "start": j}
            head = doc.lines[li].text
            current["heading"] = f"{current['heading']} / {head}" if current["heading"] else head
    current["end"] = len(words)
    if pieces and current["end"] - current["start"] < min_words:
        pieces[-1]["end"] = current["end"]
    elif current["end"] > current["start"]:
        pieces.append(current)

    chunks, n = [], 0
    for pc in pieces:
        a0, b0, head = pc["start"], pc["end"], pc["heading"]
        spans = [(a0, b0)] if b0 - a0 <= max_words else [
            (i, min(i + window, b0)) for i in range(a0, b0 - overlap, window - overlap)
        ]
        for a, b in spans:
            n += 1
            body = " ".join(words[a:b])
            if a > a0 and head:
                body = f"{head} (continued): {body}"
            chunks.append(_chunk_record(doc, units, f"{doc.doc_id}:s{n:02d}", pages[a:b], uidx[a:b], body,
                                        _unit_offsets(uidx[a:b], a, unit_starts), head))
    return chunks


CHUNKERS = {
    "fixed": lambda d, u, lu: chunk_doc(d, u, lu, config.CHUNK_WORDS, config.CHUNK_OVERLAP_WORDS),
    "section": chunk_doc_sections,
}


def time_left(start: float, done: int, total: int) -> str:
    """ "about 3 min left" from the rate so far."""
    if done >= total:
        return "almost done"
    left = (total - done) * (time.time() - start) / max(done, 1)
    return f"about {math.ceil(left / 60)} min left" if left >= 60 else "less than a minute left"


def build_collection(slug: str, name: str, keyboard: str, docs: list[Doc], skipped: list[dict],
                     source: str = "", progress=None,
                     chunkings: tuple[str, ...] = (config.DEFAULT_CHUNKING,)) -> dict:
    """Write a collection's units, chunks, manifest and embeddings. progress(fraction, message).

    Only the chunkings listed are embedded now (by default just the one the app uses); the
    others are embedded the first time someone searches with them."""
    from . import search  # here, not at the top: search imports config only, but keep ingest light

    def step(f, msg):
        if progress:
            progress(f, msg)

    out = config.collection_dir(slug)
    out.mkdir(parents=True, exist_ok=True)
    step(0.05, "Finding the sections in each note")
    built = [(d, *build_units(d)) for d in docs]
    with config.units_path(slug).open("w") as f:
        for _, units, _ in built:
            for u in units:
                f.write(json.dumps(u, ensure_ascii=False) + "\n")
    counts = {"units": sum(len(u) for _, u, _ in built)}
    for variant, chunker in CHUNKERS.items():
        chunks = [c for d, units, line_unit in built for c in chunker(d, units, line_unit)]
        path = config.chunks_path(variant, slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        counts[variant] = len(chunks)
    manifest = {
        "source": source,
        "documents": [{k: v for k, v in asdict(d).items() if k != "lines"} for d in docs],
        "skipped": skipped,
        "counts": counts,
        "fixed_chunking": {"words": config.CHUNK_WORDS, "overlap": config.CHUNK_OVERLAP_WORDS},
    }
    config.manifest_path(slug).write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    search.clear_caches()
    for variant in config.CHUNKINGS:  # drop vectors left from an earlier build of this subject
        config.embeddings_path(variant, slug).unlink(missing_ok=True)
    total = sum(counts[v] for v in chunkings)
    finished, start = 0, time.time()
    step(0.35, f"Indexing for search: 0 of {total:,} pieces")
    for variant in chunkings:
        def report(done: int, n: int, before: int = finished) -> None:
            k = before + done
            step(0.35 + 0.6 * k / max(total, 1), f"Indexing for search: {k:,} of {total:,} pieces, "
                                                 f"{time_left(start, k, total)}")
        search.build_embeddings(variant, slug, progress=report)
        finished += counts[variant]
    info = {"slug": slug, "name": name, "keyboard": keyboard, "source": source,
            "n_docs": len(docs), "n_pages": sum(d.n_pages for d in docs), "n_sections": counts["units"],
            "skipped": len(skipped)}
    config.info_path(slug).write_text(json.dumps(info, indent=2, ensure_ascii=False))
    search.clear_caches()
    step(1.0, "Done")
    return info


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Build a collection of notes for search.")
    ap.add_argument("--dir", help="folder of PDF notes (default: the vector calculus notes in local_config.json)")
    ap.add_argument("--name", help='display name, e.g. "Differential Equations"')
    ap.add_argument("--keyboard", default="general", help="symbol keyboard: vector-calculus, ode, linear-algebra, general")
    ap.add_argument("--include-drafts", action="store_true", help="also read files in folders named like 'Older Drafts'")
    args = ap.parse_args()

    if args.dir:
        name = args.name or Path(args.dir).name
        found = find_pdfs_in(Path(args.dir))
        paths = [p for p, ok in found if ok or args.include_drafts]
        docs, skipped = load_pdfs(paths, Path(args.dir).expanduser())
        skipped += [{"file": p.name, "reason": "looks like a draft"} for p, ok in found if not ok and not args.include_drafts]
        slug, keyboard, source = config.slugify(name), args.keyboard, str(Path(args.dir).expanduser())
    else:
        cfg = config.load_local_config()
        docs, skipped = load_docs(cfg)
        slug, name, keyboard, source = config.DEFAULT_COLLECTION, "Vector Calculus", "vector-calculus", cfg["notes_dir"]
    info = build_collection(slug, name, keyboard, docs, skipped, source, chunkings=config.CHUNKINGS,
                            progress=lambda f, m: print(f"  {m}") if m.startswith("Index") else None)
    print(f"[{slug}] {info['n_docs']} documents, {info['n_pages']} pages -> {info['n_sections']} sections; "
          f"skipped {info['skipped']} files (see {config.manifest_path(slug).relative_to(config.ROOT)})")


if __name__ == "__main__":
    main()
