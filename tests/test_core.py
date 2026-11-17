"""Unit tests that need no notes, no model download and no API key.

    python -m unittest discover tests
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import sympy as sp

from vctutor import ingest, mathtools
from vctutor.answer import answer, extract_final
from vctutor.tools import run_tool


class TestMathCleanup(unittest.TestCase):
    def test_cmex_letters_become_symbols(self):
        self.assertEqual(ingest._fix_span("ZZ", "CMEX10"), "∫∫")
        self.assertEqual(ingest._fix_span("I", "CMEX10"), "∮")
        self.assertEqual(ingest._fix_span("Z", "CMR12"), "Z")  # normal text is untouched

    def test_stretchy_bracket_codes(self):
        self.assertEqual(ingest._fix_span("\x12\x13", "CMEX10"), "()")

    def test_file_names(self):
        doc_id, title, chapter, sections, kind = ingest.parse_name(Path("13.2.2 - Line Integrals (Lecture 34).pdf"))
        self.assertEqual((doc_id, title, chapter, sections, kind),
                         ("13.2.2", "Line Integrals (Lecture 34)", "13", ["13.2"], "lecture"))
        doc_id, _, _, sections, kind = ingest.parse_name(
            Path("12.1.1 & 12.2.1 - Definite Integral of Two Variable Functions (Slide Deck AI).pdf"))
        self.assertEqual((doc_id, sections, kind), ("12.1.1 & 12.2.1", ["12.1", "12.2"], "slide-deck notes"))
        self.assertEqual(ingest.parse_name(Path("9.5.2. - Planes.pdf"))[0], "9.5.2")
        self.assertEqual(ingest.parse_name(Path("Exam 1 Review (Lecture 14).pdf"))[0], "review-L14")

    def test_other_file_names(self):
        doc_id, title, _, sections, _ = ingest.parse_name(
            Path("Topic 1.3 - First-Order Linear Equations (Integrating Factor) - 2026-10-22.pdf"))
        self.assertEqual((doc_id, title, sections), ("1.3", "First-Order Linear Equations (Integrating Factor)", ["1.3"]))
        doc_id, title, _, sections, kind = ingest.parse_name(Path("Week 4 notes.pdf"))
        self.assertEqual((doc_id, title, sections, kind), ("week-4-notes", "Week 4 notes", [], "notes"))


def _line(page, text, level=0, y=100.0):
    return ingest.Line(page, text, (72.0, y, 500.0, y + 12), level)


class TestChunkersAndUnits(unittest.TestCase):
    def setUp(self):
        lines = [
            _line(1, "1. Line Integrals", level=2, y=80),
            *[_line(1, "word " * 10, y=100 + 14 * i) for i in range(12)],
            _line(1, "Example 2: Work", level=2, y=300),
            _line(1, "Step 1: Parametrize", level=1, y=320),
            *[_line(1, "step " * 10, y=340 + 14 * i) for i in range(6)],
            _line(2, "Step 2: Integrate", level=1, y=80),
            *[_line(2, "green " * 10, y=100 + 14 * i) for i in range(50)],
        ]
        self.doc = ingest.Doc("13.2.2", "Line Integrals", "13", ["13.2"], "lecture", "x.pdf", lines, 2)
        self.units, self.line_unit = ingest.build_units(self.doc)

    def test_units_keep_a_worked_example_together(self):
        self.assertEqual([u["heading"] for u in self.units], ["1. Line Integrals", "Example 2: Work"])
        example = self.units[1]
        self.assertIn("Step 1: Parametrize", example["text"])
        self.assertIn("Step 2: Integrate", example["text"])  # bold step labels don't split a unit
        self.assertEqual([r["page"] for r in example["regions"]], [1, 2])

    def test_fixed_windows_point_to_units(self):
        chunks = ingest.chunk_doc(self.doc, self.units, self.line_unit, words_per_chunk=100, overlap=20)
        self.assertTrue(all(len(c["text"].split()) <= 100 for c in chunks))
        self.assertEqual(chunks[0]["chunk_id"], "13.2.2:c01")
        self.assertEqual(chunks[0]["unit_id"], "13.2.2:u01")
        self.assertEqual(chunks[-1]["unit_id"], "13.2.2:u02")

    def test_section_chunks_split_at_labels_but_map_to_the_example(self):
        chunks = ingest.chunk_doc_sections(self.doc, self.units, self.line_unit)
        step2 = [c for c in chunks if "Step 2" in c.get("heading", "")]
        self.assertTrue(step2)
        self.assertTrue(all(c["unit_id"] == "13.2.2:u02" for c in step2))  # expands back to the full example
        self.assertTrue(all(len(c["text"].split()) <= 300 + 10 for c in chunks))
        self.assertTrue(any("(continued)" in c["text"] for c in chunks))

    def test_notes_without_headings_split_by_page(self):
        lines = [_line(pg, "plain text " * 20, y=100 + 20 * i) for pg in (1, 2, 3) for i in range(15)]
        doc = ingest.Doc("week-1", "Week 1", "", [], "notes", "w.pdf", lines, 3)
        units, _ = ingest.build_units(doc)
        self.assertEqual([u["page_start"] for u in units], [1, 2, 3])  # one long section -> one per page

    def test_running_headers_are_dropped(self):
        lines = [_line(1, "Lecture 36 (3/30)", y=760), _line(2, "Lecture 36 (3/30)", y=760),
                 _line(1, "real text", y=400), _line(2, "Only once", y=760)]
        kept = [ln.text for ln in ingest.drop_running_headers(lines, page_height=792)]
        self.assertEqual(kept, ["real text", "Only once"])

    def test_build_indexes_fixed_chunks_with_live_progress(self):
        import tempfile
        from unittest import mock

        import numpy as np

        from vctutor import config, search

        class FakeEmbedder:
            def encode(self, texts, **_):
                return np.ones((len(texts), 384), dtype=np.float32)

        msgs = []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(config, "COLLECTIONS_DIR", Path(tmp)), \
                mock.patch.object(search, "embedder", return_value=FakeEmbedder()), \
                mock.patch.object(search, "EMBED_BATCH", 2):
            ingest.build_collection("t", "Test", "general", [self.doc], [],
                                    progress=lambda f, m: msgs.append((f, m)))
            n_fixed = len(search.load_chunks("fixed", "t"))
            self.assertEqual(len(np.load(config.embeddings_path("fixed", "t"))), n_fixed)
            self.assertFalse(search.has_embeddings("section", "t"))  # indexed the first time it's used
            search.clear_caches()
        indexing = [(f, m) for f, m in msgs if m.startswith("Indexing for search")]
        self.assertGreater(len(indexing), 2)  # the bar moves during the slow step
        self.assertIn(f"{n_fixed} of {n_fixed} pieces", indexing[-1][1])
        fractions = [f for f, _ in msgs]
        self.assertEqual(fractions, sorted(fractions))

    def test_expand_to_units_merges_hits(self):
        from unittest import mock
        from vctutor import search

        units = {u["unit_id"]: u for u in self.units}
        hits = [{"chunk_id": "a", "unit_id": "13.2.2:u02", "unit_offset": 0, "score": 1},
                {"chunk_id": "b", "unit_id": "13.2.2:u02", "unit_offset": 50, "score": 0.9},
                {"chunk_id": "c", "unit_id": "13.2.2:u01", "unit_offset": 0, "score": 0.8}]
        with mock.patch.object(search, "load_units", return_value=units):
            out = search.expand_to_units(hits, max_words=10_000)
        self.assertEqual([u["unit_id"] for u in out], ["13.2.2:u02", "13.2.2:u01"])
        self.assertEqual(out[0]["matched"], ["a", "b"])
        self.assertIn("Step 1: Parametrize", out[0]["context_text"])


class TestMathtools(unittest.TestCase):
    def test_helpers(self):
        x, y, z, t = mathtools.x, mathtools.y, mathtools.z, mathtools.t
        self.assertEqual(list(mathtools.curl(mathtools.vec(x**2 * y, y * z, x * z**2))), [-y, -z**2, -x**2])
        self.assertEqual(mathtools.line_integral(mathtools.vec(y, x), mathtools.vec(t, t**2), t, 0, 1, (x, y)), 1)
        self.assertEqual(mathtools.potential(mathtools.vec(2 * x * y + 1, x**2 + 3 * y**2), (x, y)), x**2 * y + x + y**3)

    def test_grading(self):
        cases = [
            ("2pi", "2*pi", "value", True),
            ("\\frac{3\\pi}{2}", "3*pi/2", "value", True),
            ("<-y, -z^2, -x^2>", "vec(-y, -z**2, -x**2)", "vector", True),
            ("6x + 3y + 2z = 6", "6*x + 3*y + 2*z - 6", "equation", True),
            ("x^2 y + x + y^3 + 7", "x**2*y + x + y**3", "potential", True),
            ("4.98", "Rational(249, 50)", "value", True),
            ("13", "12", "value", False),
            ("(1, 2)", "vec(1, 2, 0)", "vector", False),
            ("", "1", "value", False),
        ]
        for got, expected, kind, ok in cases:
            with self.subTest(got=got):
                self.assertEqual(mathtools.grade(got or None, expected, kind)[0], ok)

    def test_unsafe_input_is_rejected(self):
        for bad in ["__import__('os').system('ls')", "().__class__", "open('x')", "lambda: 1"]:
            with self.subTest(bad=bad):
                with self.assertRaises(mathtools.UnsafeExpression):
                    mathtools.evaluate(bad)
        self.assertFalse(mathtools.grade("__import__('os')", "1", "value")[0])

    def test_answer_key_matches(self):
        questions = json.loads((Path(__file__).parent.parent / "eval" / "questions.json").read_text())
        for q in (q for q in questions if q["type"] == "computation"):
            with self.subTest(id=q["id"]):
                self.assertTrue(mathtools.equivalent(mathtools.evaluate(q["answer"]), mathtools.evaluate(q["solution"]), q["kind"]))


class TestSearchHelpers(unittest.TestCase):
    def test_normalize_query(self):
        from vctutor.search import normalize_query

        q = normalize_query("∫_C F · dr, F = ⟨e^(x−1), xy⟩, r(t) = ⟨t⁴, t³⟩, 0 ≤ t ≤ 2")
        self.assertEqual(q, "integral _C F dr, F = <e^(x-1), xy>, r(t) = <t^4, t^3>, 0 <= t <= 2")
        self.assertEqual(normalize_query("∇×F and ∇·F"), "curl F and divergence F")
        self.assertEqual(normalize_query("y″ + 3y′"), "y'' + 3y'")
        self.assertEqual(normalize_query("A⁻¹ and Aᵀ, x ∈ ℝ³"), "A inverse and A transpose , x in R ^3")
        self.assertIn("laplace transform", normalize_query("ℒ{t²}"))

    def test_keyboards_are_well_formed(self):
        from vctutor.mathbox import KEYBOARDS

        for kb in KEYBOARDS.values():
            for _, keys in kb["groups"]:
                for label, insert, back, tip in keys:
                    self.assertTrue(label and insert and tip)
                    self.assertTrue(0 <= back < len(insert) or back == 0)

    def test_collection_slugs(self):
        from vctutor import config

        self.assertEqual(config.slugify("Differential Equations!"), "differential-equations")
        self.assertEqual(config.slugify("  "), "notes")

    def test_rrf_rewards_agreement(self):
        from vctutor.search import rrf

        a = [(1, 0.9), (2, 0.8), (3, 0.7)]
        b = [(2, 9.0), (4, 8.0), (1, 7.0)]
        self.assertEqual([i for i, _ in rrf([a, b], k=4)], [2, 1, 4, 3])


class TestMethodLabels(unittest.TestCase):
    def test_matching_units(self):
        from vctutor.labels import matching_units

        units = {
            "13.3.2:u04": {"doc_id": "13.3.2", "heading": "Part 2: The Parametric Method"},
            "13.3.2:u05": {"doc_id": "13.3.2", "heading": "Parametric Examples"},
            "13.4.2:u03": {"doc_id": "13.4.2", "heading": "Parametric Method (The Last Resort)"},
            "12.8.2:u02": {"doc_id": "12.8.2", "heading": "Cylindrical Coordinates"},
            "12.8.2:u03": {"doc_id": "12.8.2", "heading": "Triple Integrals in Cylindrical Coordinates"},
            "13.4.1:u03": {"doc_id": "13.4.1", "heading": "2. Applying Green’s Theorem"},
        }
        self.assertEqual(matching_units(["13.3.2", "parametric method"], units), ["13.3.2:u04"])  # same doc only
        self.assertEqual(matching_units(["12.8.2", "Cylindrical Coordinates"], units), ["12.8.2:u02", "12.8.2:u03"])
        self.assertEqual(matching_units(["12.8.2", "=Cylindrical Coordinates"], units), ["12.8.2:u02"])
        self.assertEqual(matching_units(["13.4.1", "Applying Green's"], units), ["13.4.1:u03"])  # curly quote


class TestToolAndLoop(unittest.TestCase):
    def test_run_tool(self):
        self.assertEqual(run_tool("sympy", {"expression": "integrate(x*y**2, (x, 0, 2), (y, 0, 3))"}), ("18", False))
        out, is_error = run_tool("sympy", {"expression": "__import__('os')"})
        self.assertTrue(is_error)
        self.assertTrue(run_tool("nope", {})[1])

    def test_extract_final(self):
        self.assertEqual(extract_final("work...\nFINAL: (4, 4)\n"), "(4, 4)")
        self.assertEqual(extract_final("**FINAL:** `2*pi`"), "2*pi")
        self.assertIsNone(extract_final("no final line"))

    def test_tool_loop_with_fake_server(self):
        import anthropic
        import httpx2 as httpx

        sent = []

        def handler(request):
            body = json.loads(request.content)
            sent.append(body)
            if len(sent) == 1:
                content = [{"type": "thinking", "thinking": "", "signature": "s"},
                           {"type": "tool_use", "id": "toolu_1", "name": "sympy",
                            "input": {"expression": "curl(vec(x*y, y*z, z*x))"}}]
                stop = "tool_use"
            else:
                content = [{"type": "text", "text": "Done [13.5a.1:c06]\nFINAL: (-y, -z, -x)"}]
                stop = "end_turn"
            return httpx.Response(200, json={
                "id": f"msg_{len(sent)}", "type": "message", "role": "assistant", "model": body["model"],
                "content": content, "stop_reason": stop, "stop_sequence": None, "stop_details": None,
                "usage": {"input_tokens": 10, "output_tokens": 5}})

        client = anthropic.Anthropic(api_key="fake", http_client=anthropic.DefaultHttpxClient(
            transport=httpx.MockTransport(handler)))
        r = answer("curl of <xy, yz, zx>?", method="none", use_tools=True, final_line=True, client=client)
        self.assertEqual(r["final"], "(-y, -z, -x)")
        self.assertEqual(r["tool_calls"][0]["output"], "(-y, -z, -x)")
        self.assertEqual([m["role"] for m in sent[1]["messages"]], ["user", "assistant", "user"])
        self.assertEqual(sent[1]["messages"][1]["content"][0]["type"], "thinking")  # thinking passed back
        self.assertNotIn("temperature", sent[0])

    def test_method_first_rewrite(self):
        import anthropic
        import httpx2 as httpx

        from vctutor import rewrite

        sent = []

        def handler(request):
            body = json.loads(request.content)
            sent.append(body)
            text = json.dumps({"method": "parametrize the curve and integrate F(r(t)) . r'(t) dt",
                               "search_query": "parametric method line integral F(r(t)) r'(t) dt"})
            return httpx.Response(200, json={
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                "stop_sequence": None, "stop_details": None, "usage": {"input_tokens": 50, "output_tokens": 20}})

        client = anthropic.Anthropic(api_key="fake", http_client=anthropic.DefaultHttpxClient(
            transport=httpx.MockTransport(handler)))
        out = rewrite.rewrite_query("Evaluate the line integral of <y, x> along r(t) = <t, t^2>.",
                                    client=client, use_cache=False)
        self.assertIn("parametrize", out["method"])
        self.assertEqual(sent[0]["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(sent[0]["output_config"]["effort"], "low")


if __name__ == "__main__":
    unittest.main()
