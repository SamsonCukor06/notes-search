"""Three ways to find the chunks that match a question.

- "embedding": cosine similarity between BGE embeddings (meaning-based)
- "bm25":      BM25 keyword scores (word-overlap-based)
- "hybrid":    reciprocal rank fusion of the two lists

Each works on either chunking: "fixed" (220-word windows) or "section" (split at headings),
within one collection of notes (one subject).

    python -m vctutor.search build                 # embed the chunks (both chunkings)
    python -m vctutor.search "your question"       # compare the methods
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache

import numpy as np

from . import config

C = config.DEFAULT_COLLECTION
STOPWORDS = set(
    "a an and are as at be by can do does for from how i if in is it its of on or "
    "that the this to was what when where which why with you your use using find".split()
)


_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_MATH_WORDS = [  # order matters: longer symbols first
    ("∭", " triple integral "), ("∬", " double integral "), ("∮", " closed line integral "),
    ("∫", " integral "), ("∇×", " curl "), ("∇·", " divergence "), ("∇", " gradient "),
    ("ℒ⁻¹", " inverse laplace transform "), ("ℒ", " laplace transform "), ("⁻¹", " inverse "), ("ᵀ", " transpose "),
    ("‴", "'''"), ("″", "''"), ("′", "'"), ("ℝ", " R "), ("∈", " in "), ("⊆", " subset "), ("⊂", " subset "),
    ("∩", " intersect "), ("∪", " union "), ("⊥", " orthogonal "), ("≠", " not equal "), ("±", " +- "),
    ("→", " to "), ("‖", "|"),
    ("⟨", "<"), ("⟩", ">"), ("−", "-"), ("≤", "<="), ("≥", ">="), ("·", " "), ("π", "pi"),
    ("θ", "theta"), ("ρ", "rho"), ("φ", "phi"), ("√", "sqrt"),
    ("∂", " partial "), ("×", " cross "), ("∞", " infinity "), ("î", " i "), ("ĵ", " j "), ("k̂", " k "),
    # Greek letters keep the symbol (the notes' text has it) and add the word
    ("λ", "λ lambda "), ("μ", "μ mu "), ("ω", "ω omega "), ("α", "α alpha "), ("β", "β beta "),
    ("δ", "δ delta "), ("σ", "σ sigma "), ("ε", "ε epsilon "),
]


def normalize_query(q: str) -> str:
    """Write a pasted question's math symbols the way the indexed notes text spells them:
    t⁴ -> t^4, ⟨a, b⟩ -> <a, b>, ∫ -> 'integral', ∇× -> 'curl', y″ -> y''."""
    for sym, word in _MATH_WORDS[:11]:  # inverse/transpose marks before superscript digits
        q = q.replace(sym, word)
    q = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda m: "^" + m.group(0).translate(_SUPERSCRIPTS), q)
    for sym, word in _MATH_WORDS[11:]:
        q = q.replace(sym, word)
    return re.sub(r"\s+", " ", q).strip()


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def index_text(chunk: dict) -> str:
    """What gets indexed: the note's title, the heading of the section the chunk sits in
    ("contextual chunk header", e.g. "Part 2: The Parametric Method"), and the chunk text.
    The heading names the method, which the chunk's own words often don't."""
    if config.CONTEXT_HEADERS and chunk.get("unit_heading"):
        return f"{chunk['title']}\n{chunk['unit_heading']}\n{chunk['text']}"
    return f"{chunk['title']}\n{chunk['text']}"


@lru_cache(maxsize=None)
def load_chunks(chunking: str = config.DEFAULT_CHUNKING, collection: str = C) -> list[dict]:
    path = config.chunks_path(chunking, collection)
    if not path.exists():
        raise SystemExit(f"No chunks for '{collection}' yet. Run: python -m vctutor.ingest")
    return [json.loads(line) for line in path.open()]


class _OnnxEmbedder:
    """BGE-small through ONNX Runtime (fastembed): same vectors as sentence-transformers,
    without PyTorch, so the desktop app stays small."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # slow import, so lazy

        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.model = TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.MODELS_DIR))

    def encode(self, texts: list[str], batch_size: int = 32, normalize_embeddings: bool = True, **_) -> np.ndarray:
        vecs = np.array(list(self.model.embed(texts, batch_size=batch_size)), dtype=np.float32)
        if normalize_embeddings:
            vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs


@lru_cache(maxsize=1)
def embedder():
    if config.EMBED_BACKEND == "torch":
        from sentence_transformers import SentenceTransformer

        try:  # use the cached copy without touching the network
            return SentenceTransformer(config.EMBED_MODEL, local_files_only=True)
        except OSError:
            return SentenceTransformer(config.EMBED_MODEL)
    return _OnnxEmbedder()


EMBED_BATCH = 64  # chunks per progress update (about 15 s on a laptop)


def build_embeddings(chunking: str = config.DEFAULT_CHUNKING, collection: str = C, progress=None) -> np.ndarray:
    """Embed every chunk and save the vectors. This is the slow step (about 4-5 chunks a second
    on a laptop CPU), so progress(done, total) is called after each batch."""
    texts = [index_text(c) for c in load_chunks(chunking, collection)]
    parts = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = embedder().encode(texts[i:i + EMBED_BATCH], batch_size=32, normalize_embeddings=True,
                                  show_progress_bar=False)
        parts.append(np.asarray(batch, dtype=np.float32))
        if progress:
            progress(min(i + EMBED_BATCH, len(texts)), len(texts))
    vecs = np.concatenate(parts) if parts else np.zeros((0, 384), dtype=np.float32)  # BGE-small: 384 dims
    np.save(config.embeddings_path(chunking, collection), vecs)
    return vecs


def has_embeddings(chunking: str = config.DEFAULT_CHUNKING, collection: str = C) -> bool:
    return config.embeddings_path(chunking, collection).exists()


@lru_cache(maxsize=None)
def load_embeddings(chunking: str = config.DEFAULT_CHUNKING, collection: str = C) -> np.ndarray:
    path = config.embeddings_path(chunking, collection)
    if not path.exists():
        raise SystemExit(f"No {chunking} embeddings yet. Run: python -m vctutor.search --collection {collection} build")
    vecs = np.load(path)
    if len(vecs) != len(load_chunks(chunking, collection)):
        raise SystemExit("Embeddings are out of date with the chunks. Run: python -m vctutor.search build")
    return vecs


@lru_cache(maxsize=None)
def bm25(chunking: str = config.DEFAULT_CHUNKING, collection: str = C):
    from rank_bm25 import BM25Okapi

    return BM25Okapi([tokenize(index_text(c)) for c in load_chunks(chunking, collection)])


@lru_cache(maxsize=4096)
def _query_vec(query: str) -> np.ndarray:
    return embedder().encode([config.QUERY_PREFIX + query], normalize_embeddings=True)[0]


def _ranked(scores: np.ndarray, k: int) -> list[tuple[int, float]]:
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order]


def embedding_search(query: str, k: int, chunking: str, collection: str = C) -> list[tuple[int, float]]:
    return _ranked(load_embeddings(chunking, collection) @ _query_vec(query), k)


def bm25_search(query: str, k: int, chunking: str, collection: str = C) -> list[tuple[int, float]]:
    return _ranked(np.asarray(bm25(chunking, collection).get_scores(tokenize(query))), k)


def rrf(ranked_lists: list[list[tuple[int, float]]], k: int, rrf_k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: score = sum over lists of 1 / (rrf_k + rank)."""
    fused: dict[int, float] = {}
    for hits in ranked_lists:
        for rank, (i, _) in enumerate(hits, start=1):
            fused[i] = fused.get(i, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])[:k]


def hybrid_search(query: str, k: int, chunking: str, collection: str = C, pool: int = 50) -> list[tuple[int, float]]:
    return rrf([embedding_search(query, pool, chunking, collection), bm25_search(query, pool, chunking, collection)], k)


METHODS = {"embedding": embedding_search, "bm25": bm25_search, "hybrid": hybrid_search}


def search(query: str, method: str = "embedding", k: int = config.TOP_K,
           chunking: str = config.DEFAULT_CHUNKING, extra_queries: list[str] | None = None,
           pool: int = 50, collection: str = C) -> list[dict]:
    """Top-k chunks for a query, each with its score and rank.

    extra_queries (e.g. Claude's description of the solution method) are searched too,
    and all the ranked lists are merged with reciprocal rank fusion."""
    chunks = load_chunks(chunking, collection)
    query = normalize_query(query)
    if extra_queries:
        lists = [METHODS[method](q, pool, chunking, collection) for q in [query, *map(normalize_query, extra_queries)]]
        ranked = rrf(lists, k)
    else:
        ranked = METHODS[method](query, k, chunking, collection)
    return [{**chunks[i], "score": round(score, 4), "rank": r} for r, (i, score) in enumerate(ranked, start=1)]


@lru_cache(maxsize=None)
def load_units(collection: str = C) -> dict[str, dict]:
    path = config.units_path(collection)
    if not path.exists():
        raise SystemExit(f"No units for '{collection}' yet. Run: python -m vctutor.ingest")
    return {u["unit_id"]: u for u in map(json.loads, path.open())}


def clear_caches() -> None:
    """Forget loaded indexes (after a collection is built or rebuilt)."""
    for f in (load_chunks, load_embeddings, bm25, load_units):
        f.cache_clear()


def expand_to_units(hits: list[dict], max_words: int = config.UNIT_CONTEXT_WORDS, collection: str = C) -> list[dict]:
    """Small-to-big: swap each matched chunk for the whole section ("unit") it sits in, so a
    worked example comes back from its first step. Several hits in one unit merge into one.
    Units longer than max_words are clipped to a window that starts a bit before the hit."""
    units = load_units(collection)
    out: dict[str, dict] = {}
    for h in hits:
        uid = h["unit_id"]
        if uid in out:
            out[uid]["matched"].append(h["chunk_id"])
            continue
        u = dict(units[uid])
        text = u["text"]
        if u["n_words"] > max_words:  # keep the hit and the ~250 words before it
            flat = text.split()
            a = max(0, min(h.get("unit_offset", 0) - 250, len(flat) - max_words))
            text = ("... " if a else "") + " ".join(flat[a:a + max_words]) + (" ..." if a + max_words < len(flat) else "")
        out[uid] = {**u, "context_text": text, "matched": [h["chunk_id"]], "rank": len(out) + 1,
                    "score": h.get("score")}
    return list(out.values())


def main(argv: list[str]) -> None:
    collection = C
    if argv[:2] and argv[0] == "--collection":
        collection, argv = argv[1], argv[2:]
    if argv[:1] == ["build"]:
        for chunking in config.CHUNKINGS:
            vecs = build_embeddings(chunking, collection)
            print(f"[{collection}/{chunking}] embedded {len(vecs)} chunks with {config.EMBED_MODEL}")
        return
    query = " ".join(argv) or "What does Green's theorem say?"
    for chunking in config.CHUNKINGS:
        for method in METHODS:
            print(f"\n[{chunking} / {method}]")
            for h in search(query, method, chunking=chunking, collection=collection):
                print(f"  {h['rank']}. {h['chunk_id']:<22} {h['score']:>8}  {h['title']} (p. {h['page_start']})")


if __name__ == "__main__":
    main(sys.argv[1:])
