"""Course notes search: find the pages of your notes that show how to solve a problem.

    streamlit run app.py

Each subject (vector calculus, differential equations, ...) is its own collection of notes.
Add one with "Add notes": upload PDFs or point at a folder on this computer. The app only
searches and shows pages; it doesn't write answers.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import streamlit as st

from vctutor import config
from vctutor.config import has_credentials
from vctutor.ingest import build_collection, find_pdfs_in, load_pdfs
from vctutor.mathbox import KEYBOARDS, math_search_box
from vctutor.render import render_region, unit_pdf
from vctutor.search import build_embeddings, clear_caches, expand_to_units, has_embeddings, search

st.set_page_config(page_title="Notes Search", page_icon="∮", layout="centered")

EXAMPLES = {
    "vector-calculus": ["Curl of F = ⟨yz, xz, xy⟩", "Line integral along r(t) = ⟨t, t²⟩",
                        "Volume under z = 4 − x² − y²", "Flux through a sphere", "Second derivative test"],
    "ode": ["Solve y′ + 2y = eˣ", "y″ − 3y′ + 2y = 0", "Separable equation dy/dx = xy",
            "Wronskian of two solutions", "Bifurcation diagram"],
    "linear-algebra": ["Eigenvalues of a 2×2 matrix", "Determinant by cofactor expansion",
                       "Row reduce to RREF", "Null space and column space", "Gram–Schmidt"],
    "general": [],
}
PLACEHOLDERS = {
    "vector-calculus": "Paste a problem, e.g. Evaluate ∫_C F · dr where F = ⟨e^(x−1), xy⟩ and r(t) = ⟨t⁴, t³⟩, 0 ≤ t ≤ 2",
    "ode": "Paste a problem, e.g. Solve y″ + 4y′ + 4y = 0 with y(0) = 1, y′(0) = 0",
    "linear-algebra": "Paste a problem, e.g. Find the eigenvalues and eigenvectors of A = [2 1; 1 2]",
    "general": "Paste a problem or type a topic",
}

st.markdown("""
<style>
  :root { --ink: #1d1c1a; --muted: #6f6b63; --line: #e7e3da; --accent: #3d4fd6; }
  .block-container { padding-top: 1.6rem; padding-bottom: 4rem; max-width: 820px; }
  [data-testid="stHeader"] { background: transparent; }

  .topbar { display: flex; align-items: center; justify-content: space-between;
            background: #ffffff; border: 1px solid var(--line); border-radius: 999px;
            padding: 0.55rem 0.65rem 0.55rem 1.2rem; margin-bottom: 3rem;
            box-shadow: 0 1px 2px rgba(29,28,26,0.04); }
  .brand { display: flex; align-items: center; gap: 0.6rem; font-weight: 700; font-size: 1.05rem;
           color: var(--ink); white-space: nowrap; }
  .brand .mark { display: inline-grid; place-items: center; width: 2rem; height: 2rem; border-radius: 0.6rem;
                 background: var(--accent); color: #fff; font-family: Georgia, serif; font-size: 1.15rem; }

  .hero { text-align: center; margin: 0 auto 1.6rem; max-width: 640px; }
  .hero .title { font-family: Fraunces, Georgia, serif; font-weight: 500; font-size: 3.1rem; line-height: 1.08;
                 letter-spacing: -0.02em; color: var(--ink); margin: 0 0 1rem; padding: 0; }
  .hero p { font-size: 1.15rem; line-height: 1.6; color: var(--muted); margin: 0; }

  [data-testid="stButtonGroup"] > div { justify-content: center; gap: 0.5rem; }
  [data-testid="stButtonGroup"] button { background: #ffffff; border: 1px solid var(--line); border-radius: 999px;
                                         font-size: 0.95rem; padding: 0.4rem 0.95rem; }
  [data-testid="stButtonGroup"] button:hover { border-color: #c9cff6; color: var(--accent); }
  [data-testid="stPopover"] button, .st-key-add_notes button { background: transparent; border: none;
      color: var(--muted); font-size: 0.92rem; box-shadow: none; }
  [data-testid="stPopover"] button:hover, .st-key-add_notes button:hover { color: var(--accent); background: transparent; }
  .label { text-align: center; color: var(--muted); font-size: 0.95rem; margin: 1.4rem 0 0.5rem; }
  .subject-label { text-align: center; color: var(--muted); font-size: 0.85rem; text-transform: uppercase;
                   letter-spacing: 0.06em; font-weight: 600; margin: 0 0 0.4rem; }

  .results-head { display: flex; align-items: baseline; justify-content: space-between; margin: 3rem 0 1rem; }
  .results-head .title { font-family: Fraunces, Georgia, serif; font-weight: 500; font-size: 1.9rem;
                         margin: 0; padding: 0; color: var(--ink); }
  .results-head span { color: var(--muted); font-size: 0.95rem; }
  [data-testid="stExpander"] { margin-bottom: 0.9rem; }
  [data-testid="stExpander"] details { background: #ffffff; border: 1px solid var(--line); border-radius: 18px;
      box-shadow: 0 1px 2px rgba(29,28,26,0.04), 0 8px 24px rgba(29,28,26,0.05); overflow: hidden; }
  [data-testid="stExpander"] summary { padding: 0.95rem 1.2rem; }
  [data-testid="stExpander"] summary p { font-size: 1.02rem; font-weight: 600; color: var(--ink); }
  [data-testid="stExpander"] summary:hover p { color: var(--accent); }
  [data-testid="stExpanderDetails"] img { border-radius: 10px; }

  .empty { text-align: center; color: var(--muted); margin: 2rem 0 1rem; font-size: 1.05rem; line-height: 1.6; }
  .st-key-collection { align-self: center; }  /* the subject switcher */
  .footnote { text-align: center; color: #9a958b; font-size: 0.88rem; margin-top: 3rem; line-height: 1.6; }
  @media (max-width: 640px) {
    .topbar { margin-bottom: 2rem; }
    .hero .title { font-size: 2.3rem; }
    .hero p { font-size: 1.05rem; }
    .results-head { flex-direction: column; gap: 0.2rem; }
  }
</style>
""", unsafe_allow_html=True)


# ---------- labels ----------
_NOISE = re.compile(r"^([a-z]{3,4}\s*\d{3}\b|lecture\s*\d+|lecture notes|date:|dept\.? of|department of|contents|\d+$|"
                    r"vector calculus( notes| lecture notes)?$|comprehensive notes|ai-assist|based on|recap)", re.I)


def section_name(u: dict) -> str:
    """'Lecture 36: Computing Line Integrals / Part 2: The Parametric Method' -> 'The Parametric Method'."""
    title = re.sub(r"\s*\(Lecture \d+\)$", "", u["title"]).lower()

    def worded(p: str) -> bool:  # skip headings that are formulas, like "_S F . dS"
        letters = sum(c.isascii() and c.isalpha() for c in p)
        return letters >= 4 and letters >= 0.6 * len(p.replace(" ", ""))

    parts: list[str] = []
    for p in (x.strip() for x in (u.get("heading") or "").split(" / ")):
        if not p:
            continue
        if parts and (parts[-1].endswith("-") or p[0].islower()):  # a heading broken across two lines
            parts[-1] = parts[-1].rstrip("-") + ("" if parts[-1].endswith("-") else " ") + p
        else:
            parts.append(p)
    same = lambda a, b: a.lower().rstrip("s") == b.lower().rstrip("s")  # "Flux Integrals" vs "Flux Integral"
    keep = [p for p in parts if worded(p) and not _NOISE.match(p) and p.lower() not in title and not same(p, title)]
    name = re.sub(r"^(\d+(\.\d+)*\.?|part \d+:)\s*", "", keep[-1] if keep else "", flags=re.I)
    return name.rstrip(":").strip()


def source_label(u: dict) -> str:
    title = u["title"]
    lec = re.search(r"\(Lecture (\d+)\)$", title)
    if lec:
        title = f"Lecture {lec.group(1)} · {title[: lec.start()].strip()}"
    elif u.get("sections") and u["doc_id"][:1].isdigit():
        title = f"{u['doc_id']} · {title}"
    # non-breaking space and hyphen so "p. 5-6" never splits across lines
    pages = f"p. {u['page_start']}" + (f"‑{u['page_end']}" if u["page_end"] != u["page_start"] else "")
    name = section_name(u)
    return f"{title} — {name} · {pages}" if name and name.lower() not in title.lower() else f"{title} · {pages}"


@st.cache_data(show_spinner=False, max_entries=500)
def page_image(pdf_path: str, page: int, bbox: tuple[float, ...]) -> bytes:
    return render_region(pdf_path, page, list(bbox))


# ---------- adding notes ----------
@st.dialog("Add your notes", width="large")
def add_notes_dialog() -> None:
    st.markdown("Upload the PDFs for a class, or point at a folder of them on this computer. Typed or "
                "LaTeX notes work best. Scanned or handwritten pages have no text to search.")
    name = st.text_input("Subject name", placeholder="e.g. Differential Equations")
    kb_ids = list(KEYBOARDS)
    keyboard = st.selectbox("Symbol keyboard", kb_ids, format_func=lambda k: KEYBOARDS[k]["label"],
                            index=kb_ids.index("general"))
    tab_upload, tab_folder = st.tabs(["Upload PDFs", "A folder on this computer"])
    with tab_upload:
        uploads = st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True,
                                   label_visibility="collapsed")
    with tab_folder:
        folder = st.text_input("Folder", placeholder="~/Documents/fall 2026/my class/Lecture Notes")
        chosen: list[Path] = []
        if folder.strip():
            path = Path(folder.strip().strip('"')).expanduser()
            if not path.is_dir():
                st.warning("That folder doesn't exist.")
            else:
                found = find_pdfs_in(path)
                if not found:
                    st.info("No PDFs in that folder.")
                else:
                    rows = [{"Include": ok, "File": str(p.relative_to(path))} for p, ok in found]
                    edited = st.data_editor(rows, hide_index=True, use_container_width=True, height=260,
                                            column_config={"File": st.column_config.TextColumn(disabled=True)})
                    chosen = [path / r["File"] for r in edited if r["Include"]]
                    st.caption(f"{len(chosen)} of {len(found)} PDFs selected. Files in folders named like "
                               "'Older Drafts' start unchecked.")

    slug = config.slugify(name) if name.strip() else ""
    existing = {c["slug"] for c in config.list_collections()}
    if slug in existing:
        st.warning(f"A subject named “{name}” already exists. Building replaces it.")
    n_files = len(uploads or []) + len(chosen)
    if st.button("Build the index", type="primary", disabled=not (slug and n_files), use_container_width=True):
        bar = st.progress(0.0, text="Starting…")
        progress = lambda f, msg: bar.progress(min(max(f, 0.0), 1.0), text=msg)
        if uploads:  # keep copies of uploaded files, so their pages can be shown later
            dest = config.collection_dir(slug) / "pdfs"
            dest.mkdir(parents=True, exist_ok=True)
            paths, root = [], dest
            for f in uploads:
                (dest / Path(f.name).name).write_bytes(f.getbuffer())
                paths.append(dest / Path(f.name).name)
            source = "uploaded files"
        else:
            paths, root, source = chosen, Path(folder.strip().strip('"')).expanduser(), str(Path(folder).expanduser())
        docs, skipped = load_pdfs(paths, root, progress=lambda f, m: progress(0.3 * f, m))
        if not docs:
            st.error("None of these PDFs had text to search (they may be scans).")
            return
        info = build_collection(slug, name.strip(), keyboard, docs, skipped, source,
                                progress=lambda f, m: progress(0.3 + 0.7 * f, m))
        clear_caches()
        msg = f"Added {info['name']}: {info['n_docs']} notes, {info['n_pages']} pages, {info['n_sections']} sections."
        if skipped:
            msg += f" Skipped {len(skipped)}: " + "; ".join(f"{s['file']} ({s['reason']})" for s in skipped[:4])
        st.session_state.pending_collection = slug  # switched to at the top of the next run
        st.session_state.flash = msg
        st.rerun()  # closes the dialog


# ---------- header + subject ----------
collections = config.list_collections()
names = {c["slug"]: c for c in collections}
if "pending_collection" in st.session_state:  # set by the dialog or Remove, before the switcher is drawn
    st.session_state.collection = st.session_state.pop("pending_collection")
    st.session_state.query = ""
    st.session_state.nonce = st.session_state.get("nonce", 0) + 1
st.session_state.setdefault("collection", collections[0]["slug"] if collections else "")
if st.session_state.collection not in names and collections:
    st.session_state.collection = collections[0]["slug"]

st.markdown(
    '<div class="topbar"><div class="brand"><span class="mark">∮</span>Notes Search</div></div>'
    '<div class="hero"><div class="title">Search your course notes</div>'
    "<p>Paste a problem or type a topic, and the pages of your notes that cover it show up below.</p></div>",
    unsafe_allow_html=True,
)

st.session_state.setdefault("query", "")
st.session_state.setdefault("nonce", 0)


def on_subject_change() -> None:
    st.session_state.query = ""
    st.session_state.nonce += 1


if collections:
    st.markdown('<div class="subject-label">Subject</div>', unsafe_allow_html=True)
    st.segmented_control("Subject", list(names), key="collection", format_func=lambda s: names[s]["name"],
                         label_visibility="collapsed", on_change=on_subject_change)
if not collections:
    st.markdown('<div class="empty">Add the PDFs for one of your classes to get started.<br>'
                'They stay on this computer, and nothing is uploaded anywhere.</div>', unsafe_allow_html=True)
_, mid, _ = st.columns([1, 1, 1])
if mid.button("Add notes", icon=":material/add:", key="add_notes" if collections else "add_first",
              type="secondary" if collections else "primary", use_container_width=True):
    add_notes_dialog()

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

current = names.get(st.session_state.collection or "")
keyboard = (current or {}).get("keyboard", "general")


# ---------- search box + examples ----------
def use_example() -> None:
    picked = st.session_state.get("example")
    if picked:
        st.session_state.query = picked
        st.session_state.nonce += 1  # tells the box to show the new text


if current:
    submitted = math_search_box(st.session_state.query, st.session_state.nonce,
                                PLACEHOLDERS.get(keyboard, PLACEHOLDERS["general"]), keyboard=keyboard)
    if submitted is not None:
        st.session_state.query = submitted.strip()

    examples = EXAMPLES.get(keyboard, [])
    if examples:
        st.markdown('<div class="label">Or try one of these</div>', unsafe_allow_html=True)
        st.pills("Examples", examples, key="example", on_change=use_example, label_visibility="collapsed")

    # ---------- advanced settings (closed menu) ----------
    _, mid2, _ = st.columns([1, 1.2, 1])
    with mid2.popover("Advanced settings", icon=":material/tune:", use_container_width=True):
        method = st.selectbox("Search", ["hybrid", "embedding", "bm25"],
                              help="hybrid = meaning + keywords (best overall)")
        chunking = st.selectbox("Chunks", list(config.CHUNKINGS), index=0,
                                help="fixed = 220-word windows; section = split at every bold heading")
        k = st.slider("Matches to look for", 1, 10, config.TOP_K,
                      help="Each match is widened to the whole section of the notes it's in.")
        method_first = st.checkbox("Method-first search", value=False, disabled=not has_credentials(),
                                   help="Claude names the method first (e.g. 'polar coordinates') and the notes "
                                        "are searched for that too. Needs an API key.")
        show_text = st.checkbox("Show extracted text", value=False)
        show_ids = st.checkbox("Show section IDs", value=False)
        st.caption(f"{current['name']}: {current['n_docs']} notes, {current['n_pages']} pages, "
                   f"{current['n_sections']} sections.")
        if config.APP_MODE or current["slug"] != config.DEFAULT_COLLECTION:
            sure = st.checkbox(f"Remove “{current['name']}” from the app")
            if sure and st.button("Remove", type="secondary"):
                shutil.rmtree(config.collection_dir(current["slug"]))  # the index and uploaded copies only
                clear_caches()
                st.session_state.pending_collection = next(
                    (c["slug"] for c in config.list_collections() if c["slug"] != current["slug"]), "")
                st.session_state.flash = f"Removed {current['name']}. Your original files weren't touched."
                st.rerun()

    # ---------- results ----------
    query = st.session_state.query
    slug = current["slug"]
    if query and method != "bm25" and not has_embeddings(chunking, slug):
        # The app indexes only fixed chunks when notes are added; other chunkings are indexed on first use.
        bar = st.progress(0.0, text=f"Indexing the {chunking} chunks the first time you use them…")
        build_embeddings(chunking, slug, progress=lambda d, t: bar.progress(
            d / t, text=f"Indexing the {chunking} chunks the first time you use them: {d:,} of {t:,}"))
        clear_caches()
        bar.empty()
    if query:
        with st.spinner("Searching the notes…"):
            extra, method_note = None, None
            if method_first and has_credentials():
                from vctutor.rewrite import rewrite_query

                rw = rewrite_query(query)
                extra = [rw["search_query"]] if rw.get("search_query") else None
                method_note = rw.get("method")
            units = expand_to_units(search(query, method=method, k=k, chunking=chunking, extra_queries=extra,
                                           collection=slug), collection=slug)

        if not units:
            st.markdown('<div class="empty">No matching pages found. Try adding more of the problem.</div>',
                        unsafe_allow_html=True)
        else:
            n = len(units)
            st.markdown(f'<div class="results-head"><div class="title">From the notes</div>'
                        f'<span>{n} matching section{"s" if n != 1 else ""}, best first</span></div>',
                        unsafe_allow_html=True)
            if method_note:
                st.caption(f"Method: {method_note}")
            for i, u in enumerate(units, start=1):
                label = f":blue-badge[Best match] {source_label(u)}" if i == 1 else source_label(u)
                with st.expander(label, expanded=i == 1, icon=":material/menu_book:"):
                    for region in u["regions"]:
                        st.image(page_image(unit_pdf(u), region["page"], tuple(region["bbox"])), width="stretch")
                    if show_ids:
                        st.caption(f"{u['unit_id']} · matched {', '.join(u['matched'])}")
                    if show_text:
                        st.code(u["context_text"], language=None, wrap_lines=True)

st.markdown('<div class="footnote">Search can miss. If the pages don\'t fit your problem, try naming the method,<br>'
            'like "polar coordinates" or "integrating factor".</div>', unsafe_allow_html=True)
