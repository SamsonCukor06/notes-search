"""Sitting 1 smoke test: 10 hand-picked questions (5 concept, 5 computation).

For each question it prints the top-5 chunk IDs from each search method, whether the
expected section showed up, and Claude's answer (if ANTHROPIC_API_KEY is set).
This is a sanity check for a person to read, not the evaluation (that's Sitting 2).

    python -m vctutor.smoke_test            # embedding search feeds Claude
    python -m vctutor.smoke_test --method hybrid
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from . import config
from .answer import answer, has_credentials
from .search import METHODS, search

QUESTIONS_PATH = config.ROOT / "eval" / "smoke_questions.json"


def section_hit(hits: list[dict], expected: list[str]) -> bool:
    return any(s in expected for h in hits for s in h["sections"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=list(METHODS), default="embedding", help="search method that feeds Claude")
    ap.add_argument("--no-claude", action="store_true", help="retrieval only")
    args = ap.parse_args()

    questions = json.loads(QUESTIONS_PATH.read_text())
    call_claude = has_credentials() and not args.no_claude
    lines = [f"# Smoke test ({datetime.now():%Y-%m-%d %H:%M})", ""]
    lines.append(f"Answers from {config.CLAUDE_MODEL} using {args.method} search" if call_claude
                 else "Retrieval only (no ANTHROPIC_API_KEY set, so Claude wasn't called)")
    hits_by_method = {m: 0 for m in METHODS}
    total_in = total_out = 0

    for q in questions:
        lines += ["", f"## {q['id']} ({q['type']}): {q['question']}", f"Expected section: {', '.join(q['expected_sections'])}"]
        if "expected_answer" in q:
            lines.append(f"Expected answer: {q['expected_answer']}")
        for m in METHODS:
            hits = search(q["question"], method=m)
            ok = section_hit(hits, q["expected_sections"])
            hits_by_method[m] += ok
            ids = ", ".join(h["chunk_id"] for h in hits)
            lines.append(f"- {m:<9} {'HIT ' if ok else 'MISS'}  {ids}")
        top = search(q["question"], method=args.method)
        lines.append("")
        for h in top:
            lines.append(f"  {h['rank']}. {h['chunk_id']}  {h['title']} (p. {h['page_start']})")
        if call_claude:
            r = answer(q["question"], method=args.method)
            if r["usage"]:
                total_in += r["usage"]["input_tokens"]
                total_out += r["usage"]["output_tokens"]
            lines += ["", "**Answer:**", "", r["answer"] or f"(no answer: {r['stop_reason']})"]

    n = len(questions)
    lines += ["", "## Expected section in the top 5", ""]
    lines += [f"- {m}: {k}/{n}" for m, k in hits_by_method.items()]
    if call_claude:
        lines.append(f"\nTokens used: {total_in} input, {total_out} output")

    report = "\n".join(lines)
    print(report)
    config.RESULTS_DIR.mkdir(exist_ok=True)
    out = config.RESULTS_DIR / f"smoke_test_{datetime.now():%Y%m%d_%H%M}.md"
    out.write_text(report + "\n")
    print(f"\nSaved to {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
