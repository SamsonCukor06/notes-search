"""Answer a question from the notes: retrieve the top chunks, then ask Claude to answer
from them and cite the chunk IDs. Optionally let Claude call the SymPy tool.

    python -m vctutor.answer "What does the curl measure?"
    python -m vctutor.answer --method hybrid --chunking section --tools "Find the curl of <xy, yz, zx>."
    python -m vctutor.answer --method none "..."       # closed book: no notes
    python -m vctutor.answer --context chunk "..."     # send only the matched chunks, not whole sections
"""
from __future__ import annotations

import argparse
import os
import re

from . import config
from .search import expand_to_units, search
from .tools import TOOLS, run_tool

SYSTEM_PROMPT = """You are a vector calculus tutor. You answer a student's question using the excerpts from their course notes that come with the question.

How to answer:
- Take definitions, theorems and methods from the excerpts, and cite the excerpt ID in square brackets after each claim or step that uses one, for example [13.2.2:c03]. You may do the algebra and arithmetic yourself.
- If the excerpts don't cover what the question needs, say what's missing instead of filling the gap from general knowledge.
- For a computation, show the steps and give the final answer on its own line.
- Write math in LaTeX between $...$.
- The excerpts were extracted from PDFs, so display equations can be scrambled (for example, an integral's limits may appear after it, or brackets may be out of place). Read through that, and don't copy garbled math into your answer."""

CLOSED_BOOK_PROMPT = """You are a vector calculus tutor. Answer the student's question. For a computation, show the steps and give the final answer on its own line. Write math in LaTeX between $...$."""

TOOL_NOTE = """

You have a `sympy` tool that evaluates SymPy expressions exactly. Use it to check derivatives, integrals and vector operations rather than relying on mental algebra."""

HINT_NOTE = """

The student asked for a hint, not a full solution. Say which method fits and why (citing the excerpts), then show how to start: set up the first step but don't carry it out, and don't give the final answer. End by inviting them to try the next step themselves. Keep it short."""

FINAL_LINE_NOTE = """

End your reply with one line of the form `FINAL: <answer>`, written in plain SymPy syntax with no LaTeX: use ** for powers, sqrt(), pi and E; write a vector or point as (a, b, c); write a plane or other equation as an equation, for example 2*x + 3*y - z = 4."""

MAX_TOOL_ROUNDS = 8


def format_context(passages: list[dict]) -> str:
    """Passages are chunks (id = chunk_id) or whole units (id = unit_id, text = context_text)."""
    blocks = []
    for h in passages:
        pid = h.get("chunk_id") if "context_text" not in h else h["unit_id"]
        text = h.get("context_text", h["text"])
        pages = f"p. {h['page_start']}" + (f"-{h['page_end']}" if h["page_end"] != h["page_start"] else "")
        section = f' section="{h["heading"]}"' if h.get("heading") and "context_text" in h else ""
        blocks.append(f'<excerpt id="{pid}" source="{h["doc_id"]} {h["title"]}, {pages}"{section}>\n{text}\n</excerpt>')
    return "\n\n".join(blocks)


def build_user_message(question: str, passages: list[dict]) -> str:
    if not passages:
        return f"Question: {question}"
    return f"<excerpts>\n{format_context(passages)}\n</excerpts>\n\nQuestion: {question}"


has_credentials = config.has_credentials


def extract_final(text: str | None) -> str | None:
    if not text:
        return None
    found = re.findall(r"^\s*\**FINAL:?\**\s*:?\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return found[-1].strip("`$ ") if found else None


def answer(
    question: str,
    method: str = "embedding",
    k: int = config.TOP_K,
    chunking: str = config.DEFAULT_CHUNKING,
    context: str = "unit",
    collection: str = config.DEFAULT_COLLECTION,
    model: str = config.CLAUDE_MODEL,
    use_tools: bool = False,
    method_first: bool = False,
    final_line: bool = False,
    style: str = "full",
    effort: str = "medium",
    dry_run: bool = False,
    client=None,
) -> dict:
    """Retrieve k chunks (unless method == "none") and ask Claude.
    context="unit" sends each hit's whole section instead of the bare chunk ("chunk").
    method_first=True first asks Claude (cheaply) to name the solution method, and searches
    for that too (see rewrite.py). style="hint" asks for the method and first step only.
    Returns the answer plus everything used to make it."""
    can_call = not dry_run and (client is not None or has_credentials())
    rewrite = None
    if method_first and method != "none" and can_call:
        from .rewrite import rewrite_query

        rewrite = rewrite_query(question, model=model, client=client)
    extra_queries = [rewrite["search_query"]] if rewrite and rewrite["search_query"] else None
    hits = [] if method == "none" else search(question, method=method, k=k, chunking=chunking,
                                              extra_queries=extra_queries, collection=collection)
    passages = expand_to_units(hits, collection=collection) if (context == "unit" and hits) else hits
    system = (CLOSED_BOOK_PROMPT if method == "none" else SYSTEM_PROMPT) + (TOOL_NOTE if use_tools else "")
    if style == "hint":
        system += HINT_NOTE
    if final_line:
        system += FINAL_LINE_NOTE
    user_message = build_user_message(question, passages)
    result = {
        "question": question, "method": method, "chunking": chunking, "context": context, "model": model,
        "style": style,
        "use_tools": use_tools, "retrieved": [h["chunk_id"] for h in hits], "hits": hits,
        "passages": passages, "rewrite": rewrite,
        "system": system, "user_message": user_message,
        "answer": None, "final": None, "stop_reason": None, "tool_calls": [],
        "usage": dict(rewrite["usage"]) if rewrite else {"input_tokens": 0, "output_tokens": 0},
    }
    if not can_call:
        result["stop_reason"] = "dry_run" if dry_run else "no_api_key"
        return result

    import anthropic

    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]
    extra = {"tools": TOOLS} if use_tools else {}
    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = client.messages.create(
                model=model,
                max_tokens=8000,  # room for adaptive thinking plus the answer
                system=system,
                output_config={"effort": effort},
                messages=messages,
                **extra,
            )
            result["usage"]["input_tokens"] += response.usage.input_tokens
            result["usage"]["output_tokens"] += response.usage.output_tokens
            if response.stop_reason != "tool_use":
                break
            # keep every block (thinking included) and answer each tool call
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, is_error = run_tool(block.name, block.input)
                    result["tool_calls"].append({"input": block.input, "output": output, "is_error": is_error})
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error}
                    )
            messages.append({"role": "user", "content": tool_results})
    except anthropic.AuthenticationError:
        raise SystemExit("The API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.NotFoundError:
        raise SystemExit(f"Model {model!r} not found. Set VCT_CLAUDE_MODEL to a valid model ID.")
    except anthropic.RateLimitError:
        raise SystemExit("Rate limited by the API. Wait a minute and try again.")
    except anthropic.APIStatusError as e:
        raise SystemExit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise SystemExit("Couldn't reach the Claude API. Check the internet connection.")

    result["stop_reason"] = response.stop_reason
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None) if response.stop_details else None
        result["answer"] = f"(Claude declined to answer; category: {category})"
    else:
        # read text blocks by type: a response can start with thinking blocks
        result["answer"] = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "max_tokens":
            result["answer"] += "\n\n(cut off: hit max_tokens)"
        elif response.stop_reason == "tool_use":
            result["answer"] += f"\n\n(stopped after {MAX_TOOL_ROUNDS} rounds of tool calls)"
    result["final"] = extract_final(result["answer"])
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask the vector calculus tutor a question.")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--method", choices=["embedding", "bm25", "hybrid", "none"], default="embedding")
    ap.add_argument("--chunking", choices=list(config.CHUNKINGS), default=config.DEFAULT_CHUNKING)
    ap.add_argument("--k", type=int, default=config.TOP_K)
    ap.add_argument("--context", choices=["unit", "chunk"], default="unit",
                    help="send each hit's whole section (unit) or only the matched chunk")
    ap.add_argument("--tools", action="store_true", help="let Claude call the SymPy tool")
    ap.add_argument("--method-first", action="store_true", help="have Claude name the method, then search for it too")
    ap.add_argument("--hint", action="store_true", help="ask for a hint (method + first step) instead of a full solution")
    ap.add_argument("--show-context", action="store_true", help="print the excerpts sent to Claude")
    ap.add_argument("--dry-run", action="store_true", help="retrieve only; don't call Claude")
    args = ap.parse_args()
    r = answer(" ".join(args.question), method=args.method, k=args.k, chunking=args.chunking,
               context=args.context, use_tools=args.tools, method_first=args.method_first,
               style="hint" if args.hint else "full", dry_run=args.dry_run)
    if r["rewrite"]:
        print(f"Method: {r['rewrite']['method']}  |  searched for: {r['rewrite']['search_query']}")
    print("Retrieved:", ", ".join(r["retrieved"]) or "(none: closed book)")
    if args.show_context:
        print("\n" + r["user_message"])
    if r["stop_reason"] == "no_api_key":
        print("\nNo ANTHROPIC_API_KEY set, so Claude wasn't called (retrieval only).")
    elif r["answer"]:
        for call in r["tool_calls"]:
            print(f"[sympy] {call['input'].get('expression')} -> {call['output']}")
        print("\n" + r["answer"])


if __name__ == "__main__":
    main()
