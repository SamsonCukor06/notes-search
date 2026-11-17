"""Method-first search: before searching, a cheap Claude call names the method that solves
the question and writes a search query in the words the notes would use for that method.

A question like "Evaluate the line integral of F = <e^(x-1), xy> along r(t) = <t^4, t^3>"
mentions "line integral" but not the method (parametrize the curve, then integrate
F(r(t)) . r'(t) dt), so plain search returns general line-integral notes. Searching for the
method as well fixes that. The same goes for problems that need polar coordinates but never
say "polar".
"""
from __future__ import annotations

import json

from . import config

REWRITE_PROMPT = """You help search a student's vector calculus lecture notes.

For the question below, name the method a student would use to solve it, then write a search query of 5 to 15 words using the terms lecture notes would use for that method and its steps. Don't solve the problem.

Examples of methods: "parametrize the curve and integrate F(r(t)) . r'(t) dt", "switch to polar coordinates, dA = r dr dtheta", "Green's theorem: double integral of Q_x - P_y", "check whether F is conservative and use a potential function", "Divergence Theorem: triple integral of div F".

<question>
{question}
</question>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "method": {"type": "string", "description": "The solution method, in one short phrase."},
        "search_query": {"type": "string", "description": "5 to 15 words to search the notes with."},
    },
    "required": ["method", "search_query"],
    "additionalProperties": False,
}

CACHE_PATH = config.DATA_DIR / "rewrites.json"  # avoids paying twice for the same question


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, ValueError):
        return {}


def rewrite_query(question: str, model: str = config.CLAUDE_MODEL, client=None, use_cache: bool = True) -> dict:
    """Returns {"method", "search_query", "usage"}. Raises SystemExit on API errors."""
    use_cache = use_cache and client is None  # a passed-in client is a test or fake: don't cache its output
    key = f"{model}::{question}"
    cache = _load_cache() if use_cache else {}
    if key in cache:
        return {**cache[key], "usage": {"input_tokens": 0, "output_tokens": 0}, "cached": True}

    import anthropic

    client = client or anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,  # room for a little thinking plus a short JSON answer
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(question=question)}],
        )
    except anthropic.AuthenticationError:
        raise SystemExit("The API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.APIStatusError as e:
        raise SystemExit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise SystemExit("Couldn't reach the Claude API. Check the internet connection.")

    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    if response.stop_reason in ("refusal", "max_tokens"):
        return {"method": "", "search_query": "", "usage": usage}
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    data = json.loads(text)
    out = {"method": data.get("method", ""), "search_query": data.get("search_query", "")}
    if use_cache and out["search_query"]:
        cache[key] = out
        config.DATA_DIR.mkdir(exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return {**out, "usage": usage}
