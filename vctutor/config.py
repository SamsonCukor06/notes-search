"""Paths, model names and settings in one place.

Notes are organized into collections, one per subject ("vector-calculus",
"differential-equations", ...). Each has its own folder under data/collections/ with its
chunks, sections ("units"), embeddings and a collection.json describing it.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Built from the notes; private, never committed. The desktop app points this at the user's
# own app-data folder (NOTES_SEARCH_DATA), so each person's notes stay on their computer.
DATA_DIR = Path(os.environ.get("NOTES_SEARCH_DATA", ROOT / "data")).expanduser()
RESULTS_DIR = Path(os.environ.get("NOTES_SEARCH_RESULTS", ROOT / "results")).expanduser()  # experiment output
MODELS_DIR = Path(os.environ.get("NOTES_SEARCH_MODELS", DATA_DIR / "models")).expanduser()  # the search model
APP_MODE = os.environ.get("NOTES_SEARCH_APP") == "1"  # running as the desktop app
COLLECTIONS_DIR = DATA_DIR / "collections"
DEFAULT_COLLECTION = "vector-calculus"  # the one the test set and experiments use
UNIT_CONTEXT_WORDS = 900  # longest unit text sent to Claude; longer units are clipped around the hit
CHUNKINGS = ("fixed", "section")  # fixed-size windows vs. split at the notes' headings
DEFAULT_CHUNKING = "fixed"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "notes"


def collection_dir(collection: str = DEFAULT_COLLECTION) -> Path:
    return COLLECTIONS_DIR / collection


def chunks_path(chunking: str = DEFAULT_CHUNKING, collection: str = DEFAULT_COLLECTION) -> Path:
    return collection_dir(collection) / chunking / "chunks.jsonl"


def embeddings_path(chunking: str = DEFAULT_CHUNKING, collection: str = DEFAULT_COLLECTION) -> Path:
    return collection_dir(collection) / chunking / "embeddings.npy"


def units_path(collection: str = DEFAULT_COLLECTION) -> Path:
    return collection_dir(collection) / "units.jsonl"


def manifest_path(collection: str = DEFAULT_COLLECTION) -> Path:
    return collection_dir(collection) / "manifest.json"


def info_path(collection: str = DEFAULT_COLLECTION) -> Path:
    return collection_dir(collection) / "collection.json"


def list_collections() -> list[dict]:
    """Every collection that has been built, as its collection.json (the default one first)."""
    out = []
    if COLLECTIONS_DIR.is_dir():
        for d in sorted(COLLECTIONS_DIR.iterdir()):
            info = d / "collection.json"
            if info.exists() and (d / "units.jsonl").exists():
                out.append(json.loads(info.read_text()))
    return sorted(out, key=lambda c: (c["slug"] != DEFAULT_COLLECTION, c["name"].lower()))


LOCAL_CONFIG_PATH = ROOT / "local_config.json"

# Free local embedding model (384-dim, runs on a laptop CPU). It runs through ONNX Runtime
# (fastembed, a 67 MB model file); VCT_EMBED_BACKEND=torch uses sentence-transformers instead.
# Both give the same vectors (cosine 1.0000 on the notes).
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_BACKEND = os.environ.get("VCT_EMBED_BACKEND", "onnx")
# BGE v1.5 recommends this instruction on queries (not on passages) for retrieval.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Cheap model for development; override with VCT_CLAUDE_MODEL.
CLAUDE_MODEL = os.environ.get("VCT_CLAUDE_MODEL", "claude-haiku-5-5")

TOP_K = 5
# Add each chunk's section heading to the text that gets indexed (set VCT_CONTEXT_HEADERS=0 to compare)
CONTEXT_HEADERS = os.environ.get("VCT_CONTEXT_HEADERS", "1") != "0"
CHUNK_WORDS = 220  # baseline: fixed-size word windows
CHUNK_OVERLAP_WORDS = 40


def load_local_config() -> dict:
    """Read local_config.json (gitignored): where the vector calculus notes live and what to skip."""
    if not LOCAL_CONFIG_PATH.exists():
        raise SystemExit(
            f"Missing {LOCAL_CONFIG_PATH.name}. Copy local_config.example.json to "
            "local_config.json and set notes_dir to your folder of PDF notes."
        )
    cfg = json.loads(LOCAL_CONFIG_PATH.read_text())
    cfg["notes_dir"] = str(Path(cfg["notes_dir"]).expanduser())
    cfg.setdefault("exclude_dirs", [])
    cfg.setdefault("exclude_files", [])
    return cfg


def has_credentials() -> bool:
    """Is a Claude API key (or token) set? Only method-first search and answers need one."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
