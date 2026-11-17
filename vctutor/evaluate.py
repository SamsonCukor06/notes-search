"""Experiments on the test set (eval/questions.json).

    python -m vctutor.evaluate retrieval      # no API key needed
    python -m vctutor.evaluate retrieval --method-first   # Claude names each method first (key needed)
    python -m vctutor.evaluate answers        # needs ANTHROPIC_API_KEY; ~50 problems x 6 setups

Retrieval: for every chunking x search method, does a chunk from the expected section show
up in the top k? Reports recall@1, recall@5 and MRR@10 (1 / rank of the first good chunk).

Answers: for each setup, Claude answers the 50 computation problems and SymPy grades the
FINAL line against the answer key. Setups: closed book, basic RAG, section chunks, hybrid
search, whole sections as context ("units"), and that plus the SymPy tool.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

from . import config
from .build_eval import load_questions
from .mathtools import grade
from .labels import load_method_labels, method_units
from .search import METHODS, load_units, search

ANSWER_SETUPS = {  # each adds one change, so the table shows what each change is worth
    "closed_book": dict(method="none"),
    "basic_rag": dict(method="embedding", chunking="fixed", context="chunk"),
    "section_chunks": dict(method="embedding", chunking="section", context="chunk"),
    "hybrid": dict(method="hybrid", chunking="fixed", context="chunk"),
    "hybrid_units": dict(method="hybrid", chunking="fixed", context="unit"),
    "method_first": dict(method="hybrid", chunking="fixed", context="unit", method_first=True),
    "method_first_sympy": dict(method="hybrid", chunking="fixed", context="unit", method_first=True, use_tools=True),
}


def first_good_rank(hits: list[dict], expected: list[str], review_ok: bool = False) -> int | None:
    """Rank of the first chunk from an expected section. With review_ok, a chunk from an
    exam-review lecture (which covers many sections) also counts."""
    for h in hits:
        if any(s in expected for s in h["sections"]) or (review_ok and "review" in h["sections"]):
            return h["rank"]
    return None


def retrieval_experiment(questions: list[dict], depth: int = 10, method_first: bool = False) -> dict:
    """With method_first, every question also gets Claude's method query (needs an API key)."""
    extra = {}
    if method_first:
        from .rewrite import rewrite_query

        extra = {q["id"]: [rewrite_query(q["question"])["search_query"]] for q in questions}
    units = load_units()
    labeled = {q["id"]: method_units(q["id"], units) for q in questions if q["id"] in load_method_labels()}
    rows, rows_lenient, rows_method = {}, {}, {}
    per_question = []
    for chunking in config.CHUNKINGS:
        for method in METHODS:
            ranks, lenient, mranks = [], [], []
            for q in questions:
                hits = search(q["question"], method=method, k=depth, chunking=chunking,
                              extra_queries=extra.get(q["id"]))
                rank = first_good_rank(hits, q["expected_sections"])
                ranks.append(rank)
                lenient.append(first_good_rank(hits, q["expected_sections"], review_ok=True))
                mrank = None
                if q["id"] in labeled:
                    mrank = next((h["rank"] for h in hits if h["unit_id"] in labeled[q["id"]]), None)
                    mranks.append(mrank)
                per_question.append({"id": q["id"], "chunking": chunking, "method": method, "rank": rank,
                                     "method_rank": mrank, "top5": [h["chunk_id"] for h in hits[:5]]})
            rows[(chunking, method)] = ranks
            rows_lenient[(chunking, method)] = lenient
            rows_method[(chunking, method)] = mranks
    return {"rows": rows, "rows_lenient": rows_lenient, "rows_method": rows_method,
            "method_ids": [q["id"] for q in questions if q["id"] in labeled], "per_question": per_question}


def _metrics(ranks: list[int | None]) -> dict:
    n = len(ranks)
    return {
        "n": n,
        "recall@1": sum(1 for r in ranks if r == 1) / n,
        "recall@5": sum(1 for r in ranks if r is not None and r <= 5) / n,
        "mrr@10": sum(1 / r for r in ranks if r is not None) / n,
    }


def report_retrieval(questions: list[dict], method_first: bool = False) -> str:
    res = retrieval_experiment(questions, method_first=method_first)
    groups = {
        "all": [True] * len(questions),
        "concept": [q["type"] == "concept" for q in questions],
        "computation": [q["type"] == "computation" for q in questions],
    }
    title = "Retrieval experiment" + (" with method-first queries" if method_first else "")
    lines = [f"# {title} ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"{len(questions)} questions. A hit = a chunk from the expected section. "
             "MRR@10 = average of 1/rank of the first hit (0 if none in the top 10).", ""]
    summary = {}
    for gname, mask in groups.items():
        lines += [f"## {gname} ({sum(mask)} questions)", "",
                  "| Chunking | Method | recall@1 | recall@5 | MRR@10 | recall@5 if review notes count |",
                  "|---|---|---|---|---|---|"]
        for (chunking, method), ranks in res["rows"].items():
            m = _metrics([r for r, keep in zip(ranks, mask) if keep])
            ml = _metrics([r for r, keep in zip(res["rows_lenient"][(chunking, method)], mask) if keep])
            m["recall@5_review_ok"] = ml["recall@5"]
            summary[f"{gname}/{chunking}/{method}"] = m
            lines.append(f"| {chunking} | {method} | {m['recall@1']:.0%} | {m['recall@5']:.0%} | "
                         f"{m['mrr@10']:.2f} | {ml['recall@5']:.0%} |")
        lines.append("")
    if res["method_ids"]:
        n = len(res["method_ids"])
        lines += [f"## Method level ({n} computation problems)", "",
                  "A hit = a chunk from a section of the notes that shows the problem's solution method "
                  "(hand labels in eval/private/method_labels.json), not just the right topic.", "",
                  "| Chunking | Method | recall@1 | recall@5 | MRR@10 | topic-level recall@1 (same problems) |",
                  "|---|---|---|---|---|---|"]
        comp_mask = [q["id"] in set(res["method_ids"]) for q in questions]
        for (chunking, method), mranks in res["rows_method"].items():
            m = _metrics(mranks)
            topic = _metrics([r for r, keep in zip(res["rows"][(chunking, method)], comp_mask) if keep])
            summary[f"method/{chunking}/{method}"] = m
            lines.append(f"| {chunking} | {method} | {m['recall@1']:.0%} | {m['recall@5']:.0%} | "
                         f"{m['mrr@10']:.2f} | {topic['recall@1']:.0%} |")
        lines += ["", "Method misses (no method section in the top 5):", ""]
        for (chunking, method), mranks in res["rows_method"].items():
            miss = [qid for qid, r in zip(res["method_ids"], mranks) if r is None or r > 5]
            lines.append(f"- {chunking}/{method}: {', '.join(miss) or 'none'}")
        lines.append("")
    # which questions miss the top 5 in each setup
    lines += ["## Misses (expected section not in the top 5)", ""]
    for (chunking, method), ranks in res["rows"].items():
        miss = [q["id"] for q, r in zip(questions, ranks) if r is None or r > 5]
        lines.append(f"- {chunking}/{method}: {', '.join(miss) or 'none'}")
    lines.append("")
    stamp = ("method_first_" if method_first else "") + datetime.now().strftime("%Y%m%d_%H%M")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    (config.RESULTS_DIR / f"retrieval_{stamp}.json").write_text(
        json.dumps({"summary": summary, "per_question": res["per_question"]}, indent=1))
    report = "\n".join(lines)
    (config.RESULTS_DIR / f"retrieval_{stamp}.md").write_text(report + "\n")
    return report


def answers_experiment(questions: list[dict], setups: list[str], limit: int | None, model: str) -> str:
    from .answer import answer, has_credentials

    if not has_credentials():
        raise SystemExit("Set ANTHROPIC_API_KEY first (see the README).")
    problems = [q for q in questions if q["type"] == "computation"][:limit]
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    log_path = config.RESULTS_DIR / f"answers_{stamp}.jsonl"
    scores: dict[str, list[bool]] = {}
    tokens: dict[str, list[int]] = {}
    with log_path.open("w") as log:
        for name in setups:
            opts = ANSWER_SETUPS[name]
            scores[name], tokens[name] = [], [0, 0]
            for q in problems:
                t0 = time.time()
                r = answer(q["question"], model=model, final_line=True, **opts)
                ok, note = grade(r["final"], q["solution"], q["kind"])
                scores[name].append(ok)
                tokens[name][0] += r["usage"]["input_tokens"]
                tokens[name][1] += r["usage"]["output_tokens"]
                log.write(json.dumps({
                    "setup": name, "id": q["id"], "correct": ok, "note": note, "final": r["final"],
                    "expected": q["answer"], "retrieved": r["retrieved"], "tool_calls": r["tool_calls"],
                    "usage": r["usage"], "seconds": round(time.time() - t0, 1), "answer": r["answer"],
                }, ensure_ascii=False) + "\n")
                print(f"{name:<22} {q['id']}  {'ok ' if ok else 'BAD'}  {r['final']!s:<40.40} {note}")
    n = len(problems)
    base = scores.get("closed_book")
    lines = [f"# Answer experiment ({datetime.now():%Y-%m-%d %H:%M})", "",
             f"{n} computation problems, model {model}, graded by SymPy against the answer key.", "",
             "| Setup | Correct | Accuracy | Input tokens | Output tokens |", "|---|---|---|---|---|"]
    for name, s in scores.items():
        lines.append(f"| {name} | {sum(s)}/{n} | {sum(s) / n:.0%} | {tokens[name][0]:,} | {tokens[name][1]:,} |")
    if base:
        lines += ["", "Changes vs. closed book (problems newly right / newly wrong):", ""]
        for name, s in scores.items():
            if name != "closed_book":
                gained = sum(1 for a, b in zip(base, s) if b and not a)
                lost = sum(1 for a, b in zip(base, s) if a and not b)
                lines.append(f"- {name}: +{gained} / -{lost}")
    lines += ["", f"Per-problem log: {log_path.relative_to(config.ROOT)}"]
    report = "\n".join(lines)
    (config.RESULTS_DIR / f"answers_{stamp}.md").write_text(report + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("retrieval")
    r.add_argument("--method-first", action="store_true",
                   help="also search for Claude's description of the method (needs ANTHROPIC_API_KEY)")
    a = sub.add_parser("answers")
    a.add_argument("--setups", nargs="+", choices=list(ANSWER_SETUPS), default=list(ANSWER_SETUPS))
    a.add_argument("--limit", type=int, help="only the first N problems (a cheap trial run)")
    a.add_argument("--model", default=config.CLAUDE_MODEL)
    args = ap.parse_args()
    questions = load_questions()
    if args.cmd == "retrieval":
        print(report_retrieval(questions, method_first=args.method_first))
    else:
        print(answers_experiment(questions, args.setups, args.limit, args.model))


if __name__ == "__main__":
    main()
