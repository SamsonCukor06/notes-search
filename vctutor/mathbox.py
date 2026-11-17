"""The search box: a text area with a clickable keyboard of math symbols underneath.

Clicking a key inserts its symbol where the cursor is (templates like ⟨ ⟩ and √( ) put
the cursor inside). Enter searches; Shift+Enter starts a new line. Each subject has its
own keyboard (KEYBOARDS). Built as a Streamlit custom component (st.components.v2) so it
can edit the text at the cursor.
"""
from __future__ import annotations

import streamlit as st

# key = (label shown, text inserted, how far to move the cursor back, tooltip)
KEYBOARDS = {
    "vector-calculus": {"label": "Vector calculus", "groups": [
        ("Calculus", [("∫", "∫", 0, "Integral"), ("∬", "∬", 0, "Double integral"), ("∭", "∭", 0, "Triple integral"),
                      ("∮", "∮", 0, "Closed line integral"), ("∂", "∂", 0, "Partial derivative"),
                      ("∇", "∇", 0, "Gradient"), ("∇×", "∇×", 0, "Curl"), ("∇·", "∇·", 0, "Divergence")]),
        ("Vectors", [("⟨ ⟩", "⟨⟩", 1, "Vector ⟨a, b, c⟩"), ("·", " · ", 0, "Dot product"), ("×", " × ", 0, "Cross product"),
                     ("|v|", "||", 1, "Magnitude"), ("î", "î", 0, "i-hat"), ("ĵ", "ĵ", 0, "j-hat"), ("k̂", "k̂", 0, "k-hat")]),
        ("Powers", [("x²", "²", 0, "Squared"), ("x³", "³", 0, "Cubed"), ("xⁿ", "^", 0, "Power"),
                    ("√", "√()", 1, "Square root"), ("eˣ", "e^()", 1, "e to a power")]),
        ("Symbols", [("π", "π", 0, "pi"), ("θ", "θ", 0, "theta"), ("φ", "φ", 0, "phi"), ("ρ", "ρ", 0, "rho"),
                     ("∞", "∞", 0, "Infinity"), ("≤", " ≤ ", 0, "Less than or equal"), ("≥", " ≥ ", 0, "Greater than or equal")]),
    ]},
    "ode": {"label": "Differential equations", "groups": [
        ("Derivatives", [("y′", "′", 0, "First derivative (prime)"), ("y″", "″", 0, "Second derivative"),
                         ("y‴", "‴", 0, "Third derivative"), ("dy/dx", "dy/dx", 0, "dy/dx"),
                         ("d²y/dx²", "d²y/dx²", 0, "Second derivative"), ("∂", "∂", 0, "Partial derivative"),
                         ("∫", "∫", 0, "Integral")]),
        ("Transforms", [("ℒ{ }", "ℒ{}", 1, "Laplace transform"), ("ℒ⁻¹{ }", "ℒ⁻¹{}", 1, "Inverse Laplace transform"),
                        ("eˣ", "e^()", 1, "e to a power"), ("ln", "ln()", 1, "Natural log"), ("δ", "δ", 0, "Delta")]),
        ("Powers", [("x²", "²", 0, "Squared"), ("x³", "³", 0, "Cubed"), ("xⁿ", "^", 0, "Power"),
                    ("√", "√()", 1, "Square root")]),
        ("Symbols", [("λ", "λ", 0, "lambda"), ("μ", "μ", 0, "mu"), ("ω", "ω", 0, "omega"), ("α", "α", 0, "alpha"),
                     ("β", "β", 0, "beta"), ("π", "π", 0, "pi"), ("±", "±", 0, "Plus or minus"),
                     ("∞", "∞", 0, "Infinity"), ("→", " → ", 0, "Approaches")]),
    ]},
    "linear-algebra": {"label": "Linear algebra", "groups": [
        ("Matrices", [("Aᵀ", "ᵀ", 0, "Transpose"), ("A⁻¹", "⁻¹", 0, "Inverse"), ("det", "det()", 1, "Determinant"),
                      ("[ ]", "[]", 1, "Matrix or vector"), ("rank", "rank()", 1, "Rank"), ("tr", "tr()", 1, "Trace")]),
        ("Vectors", [("⟨ ⟩", "⟨⟩", 1, "Vector"), ("‖v‖", "‖‖", 1, "Norm"), ("·", " · ", 0, "Dot product"),
                     ("×", " × ", 0, "Cross product"), ("⊥", " ⊥ ", 0, "Orthogonal"), ("span", "span{}", 1, "Span")]),
        ("Sets", [("ℝⁿ", "ℝ^", 0, "R^n"), ("∈", " ∈ ", 0, "In"), ("⊆", " ⊆ ", 0, "Subspace of"),
                  ("∩", " ∩ ", 0, "Intersection"), ("∪", " ∪ ", 0, "Union"), ("{ }", "{}", 1, "Set")]),
        ("Symbols", [("λ", "λ", 0, "lambda (eigenvalue)"), ("μ", "μ", 0, "mu"), ("α", "α", 0, "alpha"),
                     ("β", "β", 0, "beta"), ("θ", "θ", 0, "theta"), ("x²", "²", 0, "Squared"),
                     ("≠", " ≠ ", 0, "Not equal"), ("→", " → ", 0, "Maps to")]),
    ]},
    "general": {"label": "General math", "groups": [
        ("Calculus", [("∫", "∫", 0, "Integral"), ("∂", "∂", 0, "Partial derivative"), ("∇", "∇", 0, "Gradient"),
                      ("y′", "′", 0, "Prime"), ("dy/dx", "dy/dx", 0, "dy/dx"), ("∑", "∑", 0, "Sum"), ("∞", "∞", 0, "Infinity")]),
        ("Algebra", [("x²", "²", 0, "Squared"), ("x³", "³", 0, "Cubed"), ("xⁿ", "^", 0, "Power"),
                     ("√", "√()", 1, "Square root"), ("eˣ", "e^()", 1, "e to a power"), ("ln", "ln()", 1, "Natural log"),
                     ("±", "±", 0, "Plus or minus")]),
        ("Greek", [("π", "π", 0, "pi"), ("θ", "θ", 0, "theta"), ("λ", "λ", 0, "lambda"), ("μ", "μ", 0, "mu"),
                   ("σ", "σ", 0, "sigma"), ("α", "α", 0, "alpha"), ("β", "β", 0, "beta")]),
        ("Relations", [("≤", " ≤ ", 0, "Less than or equal"), ("≥", " ≥ ", 0, "Greater than or equal"),
                       ("≠", " ≠ ", 0, "Not equal"), ("≈", " ≈ ", 0, "Approximately"), ("→", " → ", 0, "Approaches"),
                       ("∈", " ∈ ", 0, "In")]),
    ]},
}

HTML = """
<div class="box">
  <textarea class="input" rows="3" spellcheck="false"></textarea>
  <div class="keyboard"></div>
  <div class="actions">
    <span class="hint">Enter to search · Shift + Enter for a new line</span>
    <div class="buttons">
      <button type="button" class="clear">Clear</button>
      <button type="button" class="go">Find the pages</button>
    </div>
  </div>
</div>
"""

CSS = """
.box {
  background: #ffffff; border: 1px solid #e7e3da; border-radius: 22px;
  box-shadow: 0 1px 2px rgba(29, 28, 26, 0.04), 0 10px 30px rgba(29, 28, 26, 0.06);
  padding: 18px 20px 16px; font-family: Inter, system-ui, sans-serif; color: #1d1c1a;
}
.input {
  width: 100%; box-sizing: border-box; border: none; outline: none; resize: vertical;
  font: 500 1.2rem/1.55 Inter, system-ui, sans-serif; color: #1d1c1a; background: transparent;
  min-height: 92px; padding: 4px 2px;
}
.input::placeholder { color: #a19c92; font-weight: 400; }
.keyboard { border-top: 1px solid #efebe3; margin-top: 10px; padding-top: 12px; display: grid; gap: 8px; }
.group { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.group-name { width: 96px; flex: none; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
              text-transform: uppercase; color: #8b867c; }
.keys { display: flex; flex-wrap: wrap; gap: 6px; }
.key {
  min-width: 44px; height: 42px; padding: 0 10px; border-radius: 11px; cursor: pointer;
  border: 1px solid #e3ded3; background: #faf8f4; color: #1d1c1a;
  font: 500 1.12rem/1 "Cambria Math", "STIX Two Math", "Latin Modern Math", Georgia, serif;
  box-shadow: 0 1px 0 #e3ded3; transition: background 0.12s, transform 0.06s, border-color 0.12s;
}
.key:hover { background: #eef0fd; border-color: #c9cff6; }
.key:active { transform: translateY(1px); box-shadow: none; }
.actions { display: flex; align-items: center; justify-content: space-between; gap: 12px;
           margin-top: 14px; flex-wrap: wrap; }
.hint { font-size: 0.85rem; color: #8b867c; }
.buttons { display: flex; gap: 8px; margin-left: auto; }
.clear, .go { height: 46px; border-radius: 999px; padding: 0 22px; cursor: pointer;
              font: 600 1rem Inter, system-ui, sans-serif; }
.clear { background: transparent; color: #6f6b63; border: 1px solid #e3ded3; }
.clear:hover { background: #f4f1ea; }
.go { background: #3d4fd6; color: #ffffff; border: none; box-shadow: 0 6px 16px rgba(61, 79, 214, 0.28); }
.go:hover { background: #3243c4; }
@media (max-width: 560px) {
  .group { gap: 6px; } .group-name { width: 100%; }
  .key { min-width: 40px; height: 40px; }
  .hint { display: none; }
  .buttons { width: 100%; } .go { flex: 1; }
}
"""

JS = """
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  const root = parentElement;
  const box = root.querySelector('.input');
  if (data && data.placeholder) box.placeholder = data.placeholder;

  // (re)build the keys when the subject's keyboard changes
  if (data && data.keyboard !== root.__keyboard) {
    root.__keyboard = data.keyboard;
    const kb = root.querySelector('.keyboard');
    kb.replaceChildren();
    for (const [name, keys] of data.groups || []) {
      const group = document.createElement('div'); group.className = 'group';
      const label = document.createElement('span'); label.className = 'group-name'; label.textContent = name;
      const row = document.createElement('div'); row.className = 'keys';
      for (const [text, insert, back, tip] of keys) {
        const key = document.createElement('button');
        key.type = 'button'; key.className = 'key'; key.textContent = text; key.title = tip;
        key.dataset.insert = insert; key.dataset.back = back;
        row.appendChild(key);
      }
      group.append(label, row); kb.appendChild(group);
    }
  }
  // fill the box when Python sends new text (an example was picked)
  if (data && data.nonce !== undefined && root.__nonce !== data.nonce) {
    root.__nonce = data.nonce;
    if (typeof data.text === 'string') box.value = data.text;
  }
  if (root.__bound) return;  // wire up the handlers once per mount
  root.__bound = true;

  const submit = () => setTriggerValue('submitted', box.value);
  const kb = root.querySelector('.keyboard');
  kb.addEventListener('mousedown', (e) => { if (e.target.closest('.key')) e.preventDefault(); });  // keep the cursor
  kb.addEventListener('click', (e) => {
    const key = e.target.closest('.key');
    if (!key) return;
    const text = key.dataset.insert, back = parseInt(key.dataset.back || '0', 10);
    const start = box.selectionStart ?? box.value.length, end = box.selectionEnd ?? start;
    box.value = box.value.slice(0, start) + text + box.value.slice(end);
    const pos = start + text.length - back;
    box.focus();
    box.setSelectionRange(pos, pos);
  });
  box.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
  });
  root.querySelector('.go').addEventListener('click', submit);
  root.querySelector('.clear').addEventListener('click', () => { box.value = ''; box.focus(); });
}
"""

_component = st.components.v2.component("math_search_box", html=HTML, css=CSS, js=JS)


def math_search_box(text: str = "", nonce: int = 0, placeholder: str = "", keyboard: str = "vector-calculus",
                    key: str = "math_search_box"):
    """Show the box with the subject's keyboard. Returns the text when the student searches, else None."""
    groups = KEYBOARDS.get(keyboard, KEYBOARDS["general"])["groups"]
    result = _component(data={"text": text, "nonce": nonce, "placeholder": placeholder,
                              "keyboard": keyboard, "groups": groups},
                        key=key, on_submitted_change=lambda: None)
    return getattr(result, "submitted", None)
