"""Tools Claude can call while answering.

One tool: `sympy`, which evaluates a SymPy expression exactly, so Claude can check
derivatives, integrals and vector operations instead of doing the algebra in its head.
`answer.answer(..., use_tools=True)` runs the tool-use loop.
"""
from __future__ import annotations

import signal
from contextlib import contextmanager

from .mathtools import evaluate, to_text

SYMPY_TOOL = {
    "name": "sympy",
    "description": (
        "Evaluate one SymPy expression exactly and return the simplified result. Use it to check "
        "derivatives, integrals, dot and cross products, gradients, curls, divergences, line integrals "
        "and flux integrals instead of doing the algebra by hand. Real symbols x, y, z, t, u, v, r, "
        "theta, rho, phi are predefined. Helpers: vec(a, b, c); dot(a, b); cross(a, b); norm(a); unit(a); "
        "scalar_proj(b, onto); vector_proj(b, onto); angle(a, b); gradient(f, (x, y, z)); divergence(F); "
        "curl(F); curl2d(F) = Q_x - P_y; directional_derivative(f, point, direction, (x, y)); "
        "hessian_det(f); critical_point(f); potential(F, (x, y)); line_integral(F, curve, t, a, b, (x, y)) "
        "for the integral of F.dr; arc_length(curve, t, a, b); flux(F, surface, (u, a, b), (v, c, d)) "
        "oriented by r_u x r_v. Also integrate, diff, simplify, expand, factor, solve, sqrt, exp, log, "
        "sin, cos, tan, pi, E, Rational, Matrix. Write powers with **. Substitute with "
        ".subs([(x, 1), (y, 2)]). Example: integrate(x*y**2, (x, 0, 2), (y, 0, 3))"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "A single SymPy expression to evaluate."}
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS: list[dict] = [SYMPY_TOOL]
TIME_LIMIT_SECONDS = 20


class ToolTimeout(Exception):
    pass


@contextmanager
def _time_limit(seconds: int):
    def handler(signum, frame):
        raise ToolTimeout(f"took longer than {seconds} s")

    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one tool call. Returns (result text, is_error)."""
    if name != "sympy":
        return f"Unknown tool {name!r}.", True
    expr = tool_input.get("expression", "")
    try:
        with _time_limit(TIME_LIMIT_SECONDS):
            return to_text(evaluate(expr)), False
    except Exception as e:  # report every failure back to Claude so it can fix the expression
        return f"Error ({type(e).__name__}): {e}", True
