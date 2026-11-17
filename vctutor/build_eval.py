"""Compute the answer key for eval/questions.json with SymPy, and write eval/REVIEW.md
(a readable sheet for checking the questions by hand).

    python -m vctutor.build_eval
"""
from __future__ import annotations

import json
from collections import Counter

from . import config
from .labels import load_method_labels
from .mathtools import evaluate, to_text

QUESTIONS_PATH = config.ROOT / "eval" / "questions.json"
REVIEW_PATH = config.ROOT / "eval" / "REVIEW.md"
METHOD_REVIEW_PATH = config.ROOT / "eval" / "private" / "METHOD_REVIEW.md"


def load_questions() -> list[dict]:
    return json.loads(QUESTIONS_PATH.read_text())


def save_questions(questions: list[dict]) -> None:
    lines = ",\n".join("  " + json.dumps(q, ensure_ascii=False) for q in questions)
    QUESTIONS_PATH.write_text("[\n" + lines + "\n]\n")


def main() -> None:
    questions = load_questions()
    ids = [q["id"] for q in questions]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    if dupes:
        raise SystemExit(f"duplicate ids: {dupes}")
    for q in questions:
        if q["type"] == "computation":
            q["answer"] = to_text(evaluate(q["solution"]))
    save_questions(questions)

    concept = [q for q in questions if q["type"] == "concept"]
    comp = [q for q in questions if q["type"] == "computation"]
    out = [
        "# Test set: review sheet",
        "",
        f"{len(questions)} questions: {len(concept)} concept, {len(comp)} computation. "
        "Answers were computed by SymPy from each problem's `solution` in `questions.json`.",
        "",
        "Check: is each question clear, is the expected section right, and is each answer right?",
        "",
        "## Concept questions (scored by whether the expected section is in the top 5)",
        "",
        "| ID | Question | Expected section |",
        "|---|---|---|",
    ]
    out += [
        f"| {q['id']} | {q['question']}{' *(no keywords)*' if q.get('paraphrase') else ''} | {', '.join(q['expected_sections'])} |"
        for q in concept
    ]
    out += [
        "",
        "## Computation problems (answers auto-graded with SymPy)",
        "",
        "| ID | Problem | Section | Method | Answer (SymPy) | Grading |",
        "|---|---|---|---|---|---|",
    ]
    methods = load_method_labels()
    out += [
        f"| {q['id']} | {q['question']} | {', '.join(q['expected_sections'])} | "
        f"{methods.get(q['id'], {}).get('method', '')} | `{q['answer']}` | {q['kind']} |"
        for q in comp
    ]
    out += [
        "",
        "Grading kinds: **value** and **vector** must match exactly (numerically, to 1e-6); "
        "**expression** must be the same function; **equation** may differ by a constant factor "
        "(3x + 2y = 1 and 6x + 4y = 2 are the same plane); **potential** may differ by an added constant.",
    ]
    REVIEW_PATH.write_text("\n".join(out) + "\n")
    print(f"answer key built for {len(comp)} problems; review sheet -> {REVIEW_PATH.relative_to(config.ROOT)}")
    if methods:
        write_method_review(comp, methods)


def write_method_review(comp: list[dict], methods: dict) -> None:
    """Private sheet (it quotes the notes' headings): for each problem, the sections of the
    notes labeled as showing its method, so the labels can be checked against the notes."""
    from .labels import matching_units
    from .search import load_units

    units = load_units()
    out = ["# Method labels: review sheet (private)", "",
           "For each problem, the sections of your notes that show how to solve it. Search is scored on "
           "whether one of these comes up. Check that each section really shows the method, and add any "
           "that are missing (edit eval/private/method_labels.json, then rerun python -m vctutor.build_eval).", ""]
    for q in comp:
        m = methods.get(q["id"])
        if not m:
            continue
        out += [f"## {q['id']}: {q['question']}", f"Method: {m['method']}", ""]
        for ref in m["refs"]:
            for uid in matching_units(ref, units) or ["(no match!)"]:
                u = units.get(uid)
                where = f"{u['doc_id']} {u['title']}, p. {u['page_start']}" if u else ""
                out.append(f"- {uid}: {u['heading'] if u else ref} ({where})")
        out.append("")
    METHOD_REVIEW_PATH.write_text("\n".join(out) + "\n")
    print(f"method labels for {len(methods)} problems; private sheet -> {METHOD_REVIEW_PATH.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
