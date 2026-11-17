"""SymPy helpers shared by the answer key, the grader and Claude's SymPy tool.

- `evaluate(text)`: safely evaluate a SymPy expression string with vector-calculus helpers
  (gradient, curl, line_integral, flux, ...).
- `equivalent(got, expected, kind)`: decide whether two answers match.
"""
from __future__ import annotations

import random
import re

import sympy as sp

x, y, z, t, u, v = sp.symbols("x y z t u v", real=True)
r, theta, rho, phi = sp.symbols("r theta rho phi", real=True)
XYZ = (x, y, z)


# ---------- vector helpers ----------
def vec(*components) -> sp.Matrix:
    return sp.Matrix(components)


def dot(a, b):
    return sp.simplify(sp.Matrix(a).dot(sp.Matrix(b)))


def cross(a, b) -> sp.Matrix:
    return sp.Matrix(a).cross(sp.Matrix(b))


def norm(a):
    return sp.sqrt(sp.simplify(sp.Matrix(a).dot(sp.Matrix(a))))


def unit(a) -> sp.Matrix:
    return sp.simplify(sp.Matrix(a) / norm(a))


def scalar_proj(b, onto):
    """Scalar projection (component) of b onto `onto`."""
    return sp.simplify(dot(b, onto) / norm(onto))


def vector_proj(b, onto) -> sp.Matrix:
    onto = sp.Matrix(onto)
    return sp.simplify(dot(b, onto) / dot(onto, onto) * onto)


def angle(a, b):
    return sp.simplify(sp.acos(dot(a, b) / (norm(a) * norm(b))))


# ---------- calculus helpers ----------
def gradient(f, variables=XYZ) -> sp.Matrix:
    return sp.Matrix([sp.diff(f, s) for s in variables])


def divergence(F, variables=XYZ):
    return sp.simplify(sum(sp.diff(Fi, s) for Fi, s in zip(F, variables)))


def curl(F, variables=XYZ) -> sp.Matrix:
    P, Q, R = F
    a, b, c = variables
    return sp.simplify(
        sp.Matrix([sp.diff(R, b) - sp.diff(Q, c), sp.diff(P, c) - sp.diff(R, a), sp.diff(Q, a) - sp.diff(P, b)])
    )


def curl2d(F, variables=(x, y)):
    """Scalar curl Q_x - P_y of a planar field (the integrand in Green's theorem)."""
    P, Q = F
    return sp.simplify(sp.diff(Q, variables[0]) - sp.diff(P, variables[1]))


def directional_derivative(f, point, direction, variables=XYZ):
    g = gradient(f, variables).subs(dict(zip(variables, point)))
    return sp.simplify(g.dot(unit(direction)))


def hessian_det(f, variables=(x, y)):
    return sp.simplify(sp.hessian(f, variables).det())


def critical_point(f, variables=(x, y)) -> sp.Matrix:
    """The single real critical point of f (raises if there isn't exactly one)."""
    sols = sp.solve([sp.diff(f, s) for s in variables], list(variables), dict=True)
    sols = [s for s in sols if all(sp.im(val) == 0 for val in s.values())]
    if len(sols) != 1:
        raise ValueError(f"expected one critical point, found {len(sols)}")
    return sp.Matrix([sols[0][s] for s in variables])


def potential(F, variables=XYZ):
    """A potential function f with grad f = F (F must be conservative)."""
    variables = variables[: len(F)]
    f = sp.integrate(F[0], variables[0])
    for Fi, s in zip(F[1:], variables[1:]):
        f += sp.integrate(sp.simplify(Fi - sp.diff(f, s)), s)
    if any(sp.simplify(sp.diff(f, s) - Fi) != 0 for Fi, s in zip(F, variables)):
        raise ValueError("field is not conservative")
    return sp.simplify(f)


def line_integral(F, curve, param, a, b, variables=XYZ):
    """Integral of F . dr along curve(param), param from a to b."""
    sub = dict(zip(variables, curve))
    integrand = sum(Fi.subs(sub) * sp.diff(ci, param) for Fi, ci in zip(F, curve))
    return sp.simplify(sp.integrate(sp.simplify(integrand), (param, a, b)))


def arc_length(curve, param, a, b):
    speed = sp.sqrt(sp.simplify(sum(sp.diff(c, param) ** 2 for c in curve)))
    return sp.simplify(sp.integrate(sp.simplify(speed), (param, a, b)))


def flux(F, surface, ubounds, vbounds, variables=XYZ):
    """Flux of F through surface(u, v), oriented by r_u x r_v."""
    (s1, a1, b1), (s2, a2, b2) = ubounds, vbounds
    S = sp.Matrix(surface)
    normal = S.diff(s1).cross(S.diff(s2))
    Fs = sp.Matrix([Fi.subs(dict(zip(variables, surface))) for Fi in F])
    integrand = sp.simplify(Fs.dot(normal))
    return sp.simplify(sp.integrate(integrand, (s1, a1, b1), (s2, a2, b2)))


# ---------- safe evaluation ----------
_NAMESPACE = {
    name: getattr(sp, name)
    for name in (
        "sqrt exp log ln sin cos tan asin acos atan sinh cosh tanh pi E I oo Rational "
        "integrate diff simplify expand factor limit Matrix symbols Symbol Abs"
    ).split()
    if hasattr(sp, name)
}
_NAMESPACE.update(
    ln=sp.log, e=sp.E, x=x, y=y, z=z, t=t, u=u, v=v, r=r, theta=theta, rho=rho, phi=phi,
    vec=vec, dot=dot, cross=cross, norm=norm, unit=unit, scalar_proj=scalar_proj, vector_proj=vector_proj,
    angle=angle, gradient=gradient, divergence=divergence, curl=curl, curl2d=curl2d,
    directional_derivative=directional_derivative, hessian_det=hessian_det,
    critical_point=critical_point, potential=potential, solve=sp.solve,
    line_integral=line_integral, arc_length=arc_length, flux=flux,
)
_ALLOWED = re.compile(r"^[0-9A-Za-z_+\-*/^().,\[\]\s=]*$")
_BLOCKED = re.compile(r"__|\b(import|lambda|exec|eval|open|globals|locals|getattr|setattr|compile)\b")


class UnsafeExpression(ValueError):
    pass


def evaluate(text: str):
    """Evaluate a SymPy expression string with only math names available.

    Rejects anything outside a small character set and blocks dunder access, so a
    string can't reach Python internals."""
    text = text.strip().replace("^", "**")
    if not _ALLOWED.match(text) or _BLOCKED.search(text):
        raise UnsafeExpression(f"not allowed: {text!r}")
    result = eval(text, {"__builtins__": {}}, dict(_NAMESPACE))  # noqa: S307 (checked above)
    return _normalize(result)


def _normalize(value):
    if isinstance(value, (list, tuple)):
        return sp.Matrix(value)
    return value


# ---------- grading ----------
_LATEX_FIXES = [
    (r"\\left|\\right|\\,|\\!|\\;|\$", ""),
    (r"\\dfrac|\\tfrac", r"\\frac"),
    (r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))"),
    (r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)"),
    (r"\\pi", "pi"),
    (r"\\cdot|\\times", "*"),
    (r"\\langle|⟨", "("),
    (r"\\rangle|⟩", ")"),
    (r"π", "pi"),
    (r"√\(", "sqrt("),
]


def clean_answer(text: str) -> str:
    """Turn a model's final answer into something SymPy can read."""
    s = text.strip().strip("`").rstrip(".").strip()
    for pat, rep in _LATEX_FIXES:
        s = re.sub(pat, rep, s)
    s = re.sub(r"<([^<>]*)>", r"(\1)", s)  # <a, b, c> -> (a, b, c)
    return s.strip()


_PARSE_GLOBALS = {k: getattr(sp, k) for k in dir(sp) if not k.startswith("_")}
_PARSE_GLOBALS["__builtins__"] = {}


def parse_answer(text: str, kind: str):
    """Parse a model's final answer. Handles 'curl F = (...)', '3x + 2y - z = 1' (for planes),
    implicit multiplication like 2pi or x^2 y, and simple LaTeX."""
    from sympy.parsing.sympy_parser import (
        convert_xor, implicit_multiplication_application, parse_expr, standard_transformations,
    )

    s = clean_answer(text)
    if "=" in s:
        parts = [p.strip() for p in s.split("=")]
        if kind == "equation" and len(parts) == 2:
            s = f"({parts[0]}) - ({parts[1]})"
        else:
            s = parts[-1]  # 'grad f(1,2) = (4, 4)' -> '(4, 4)'
    if not _ALLOWED.match(s) or _BLOCKED.search(s):
        raise UnsafeExpression(f"not allowed: {s!r}")
    transforms = standard_transformations + (implicit_multiplication_application, convert_xor)
    value = parse_expr(s, local_dict=dict(_NAMESPACE), global_dict=dict(_PARSE_GLOBALS), transformations=transforms)
    return _normalize(value)


def grade(final_text: str | None, expected_text: str, kind: str) -> tuple[bool, str]:
    """Compare a model's FINAL answer with the answer key. Returns (correct, note)."""
    if not final_text:
        return False, "no FINAL line"
    try:
        got = parse_answer(final_text, kind)
    except Exception as e:  # unparseable answers count as wrong
        return False, f"couldn't parse: {type(e).__name__}"
    expected = evaluate(expected_text)
    try:
        return equivalent(got, expected, kind), ""
    except Exception as e:
        return False, f"compare failed: {type(e).__name__}"


def _num(expr) -> complex:
    return complex(sp.N(expr, 30))


def _close(a, b, tol=1e-6) -> bool:
    try:
        return abs(_num(a) - _num(b)) <= tol * (1 + abs(_num(b)))
    except (TypeError, ValueError):
        return False


def _same_expr(a, b) -> bool:
    if sp.simplify(a - b) == 0:
        return True
    syms = sorted((a - b).free_symbols, key=str)
    if not syms:
        return _close(a, b)
    rng = random.Random(0)
    for _ in range(4):  # numeric spot checks at random points
        pt = {s: sp.Rational(rng.randint(1, 9), rng.randint(1, 5)) for s in syms}
        if not _close(a.subs(pt), b.subs(pt)):
            return False
    return True


def equivalent(got, expected, kind: str) -> bool:
    """kind: value, vector, expression, equation (equal up to a constant factor),
    potential (equal up to an added constant)."""
    if kind == "vector":
        if not (isinstance(got, sp.MatrixBase) and isinstance(expected, sp.MatrixBase)):
            return False
        if len(got) != len(expected):
            return False
        return all(_same_expr(sp.sympify(g), sp.sympify(e)) for g, e in zip(got, expected))
    if isinstance(got, sp.MatrixBase) or isinstance(expected, sp.MatrixBase):
        return False
    got, expected = sp.sympify(got), sp.sympify(expected)
    if kind == "equation":  # a = 0 and b = 0 describe the same plane if a / b is constant
        ratio = sp.simplify(got / expected)
        return ratio != 0 and not ratio.free_symbols
    if kind == "potential":
        return all(sp.simplify(sp.diff(got - expected, s)) == 0 for s in XYZ)
    return _same_expr(got, expected)


def to_text(value) -> str:
    """Readable answer string for the answer key."""
    if isinstance(value, sp.MatrixBase):
        return "(" + ", ".join(str(sp.simplify(c)) for c in value) + ")"
    return str(sp.simplify(value))
