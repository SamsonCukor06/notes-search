"""Method-level labels for the computation problems (eval/private/method_labels.json).

Section labels ("13.3") only say a result is about the right topic. Method labels name the
sections of the notes that show how to solve the problem ("13.3.2" + "Part 2: The
Parametric Method"), so search can be scored on finding the method, not just the topic.
The file quotes the notes' headings, so it is gitignored like the notes.

    python -m vctutor.labels      # check that every label matches a section of the notes
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from . import config

LABELS_PATH = config.ROOT / "eval" / "private" / "method_labels.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("”", '"').replace("“", '"')).casefold().strip()


@lru_cache(maxsize=1)
def load_method_labels() -> dict[str, dict]:
    if not LABELS_PATH.exists():
        return {}
    data = json.loads(LABELS_PATH.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def matching_units(ref: tuple[str, str] | list[str], units: dict[str, dict]) -> list[str]:
    """Sections of doc whose heading contains the text (or equals it, if it starts with '=')."""
    doc, heading = ref
    exact = heading.startswith("=")
    h = _norm(heading.lstrip("="))
    return [uid for uid, u in units.items()
            if u["doc_id"] == doc and (h == _norm(u["heading"]) if exact else h in _norm(u["heading"]))]


def method_units(qid: str, units: dict[str, dict]) -> set[str]:
    """All unit ids that show the method for problem qid (empty if it has no labels)."""
    label = load_method_labels().get(qid)
    if not label:
        return set()
    return {uid for ref in label["refs"] for uid in matching_units(ref, units)}


def check(units: dict[str, dict]) -> list[str]:
    """Problems with the labels: refs that match no section, or more than two."""
    issues = []
    for qid, label in load_method_labels().items():
        for ref in label["refs"]:
            n = len(matching_units(ref, units))
            if n == 0:
                issues.append(f"{qid}: no section matches {ref}")
            elif n > 2:
                issues.append(f"{qid}: {ref} is vague, it matches {n} sections")
    return issues


def main() -> None:
    from .search import load_units

    units = load_units()
    labels = load_method_labels()
    issues = check(units)
    n_refs = sum(len(v["refs"]) for v in labels.values())
    print(f"{len(labels)} problems, {n_refs} refs; {len(issues)} issue(s)")
    for line in issues:
        print("  " + line)


if __name__ == "__main__":
    main()
