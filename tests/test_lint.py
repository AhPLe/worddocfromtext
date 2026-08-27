import unittest
from pathlib import Path

from builder.parser import parse_text
from builder.cuts import find_cuts
from builder.lint import lint

FIX = Path(__file__).parent / "fixtures" / "mini_master.md"

UNBALANCED = (
    "## Header\n"
    "Name line with stray close⟧ here\n"
    "\n"
    "## Notes\n"
    "⟦never closed\n"
    "still inside\n"
)

DUP_IDS = (
    "## Professional experience\n"
    "\n"
    "### X Corp — Y, Z — 2020\n"
    "**T**\n"
    "- One thing done well. <!-- id: same -->\n"
    "- Another thing done well. <!-- id: same -->\n"
)

UNKNOWN_ID = (
    "## Professional experience\n"
    "\n"
    "### X Corp — Y, Z — 2020\n"
    "**T**\n"
    "- One thing done well. <!-- id: real -->\n"
    "\n"
    "## Cut map\n"
    "\n"
    "```yaml\n"
    "cut: c1\n"
    "exclude: [nope]\n"
    "```\n"
)

DANGLING = (
    "## Professional experience\n"
    "\n"
    "### X Corp — Y, Z — 2020\n"
    "**T**\n"
    "- Ends mid-thought;\n"
)

TWO_GPA = (
    "## Education\n"
    "**A** — U1, 2016 — GPA 3.9\n"
    "also B — U2, 2012 — GPA 3.2\n"
)


def _codes(findings):
    return {(f.code, f.line) for f in findings}


class TestLint(unittest.TestCase):
    def test_unbalanced_markers_line_numbers(self):
        doc = parse_text(UNBALANCED)
        codes = _codes(doc.findings)
        self.assertIn(("slot-stray-close", 2), codes)
        self.assertIn(("slot-unclosed", 5), codes)
        # The unclosed slot swallowed its content: nothing shippable leaks.
        notes = next(s for s in doc.sections if s.heading == "Notes")
        blk = notes.blocks[0]
        self.assertTrue(blk.slots)
        self.assertEqual(blk.text, "")

    def test_duplicate_ids_error(self):
        doc = parse_text(DUP_IDS)
        codes = {f.code for f in lint(doc)}
        self.assertIn("id-duplicate", codes)

    def test_cut_referencing_unknown_id_errors(self):
        doc = parse_text(UNKNOWN_ID)
        cuts, cfind = find_cuts(doc)
        self.assertIn("c1", cuts)
        codes = {f.code for f in lint(doc, cuts) + cfind}
        self.assertIn("cut-unknown-id", codes)

    def test_fixture_style_findings(self):
        doc = parse_text(FIX.read_text(encoding="utf-8"))
        cuts, _ = find_cuts(doc)
        codes = {f.code for f in lint(doc, cuts)}
        self.assertIn("bullet-mixed", codes)          # dashboard bullet
        self.assertIn("bullet-slot-only", codes)      # DRAFT bullet
        self.assertIn("paragraph-slot-only", codes)   # summary label
        self.assertIn("entry-missing-title", codes)   # Beta LLC
        # Non-shipping sections stay quiet and error-free overall:
        self.assertFalse(any(f.severity == "ERROR" for f in lint(doc, cuts)))

    def test_bullet_length_threshold(self):
        doc = parse_text(FIX.read_text(encoding="utf-8"))
        codes = {f.code for f in lint(doc, max_bullet_len=10)}
        self.assertIn("bullet-length", codes)

    def test_dangling_bullet(self):
        codes = {f.code for f in lint(parse_text(DANGLING))}
        self.assertIn("bullet-dangling", codes)

    def test_cut_reference_validation(self):
        bad = (
            "## Summary\n"
            "Default text here.\n"
            "\n"
            "## Professional experience\n"
            "\n"
            "### X Corp — Y, Z — 2020 <!-- id: xcorp -->\n"
            "**T**\n"
            "- One thing done well. <!-- id: real -->\n"
            "\n"
            "## Cut map\n"
            "\n"
            "```yaml\n"
            "cut: c1\n"
            "include: [real]\n"
            "title_overrides:\n"
            "  ghost: \"Nope\"\n"
            "summary: summary-missing\n"
            "```\n")
        doc = parse_text(bad)
        cuts, cfind = find_cuts(doc)
        codes = {f.code for f in lint(doc, cuts) + cfind}
        self.assertIn("cut-unknown-entry", codes)    # ghost entry
        self.assertIn("cut-unknown-summary", codes)  # missing variant
        self.assertIn("include-noop", codes)         # nothing excludes 'real'

    def test_two_gpa_paragraph(self):
        codes = {f.code for f in lint(parse_text(TWO_GPA))}
        self.assertIn("paragraph-two-gpa", codes)


class TestEducationDiagnostics(unittest.TestCase):
    def _findings(self, edu_body):
        from builder.parser import parse_text
        from builder.cuts import find_cuts
        from builder.context import build_context
        doc = parse_text("# X\n\n## Education\n" + edu_body, source="t")
        cuts, _ = find_cuts(doc)
        _, bf = build_context(doc, cuts)
        return {f.code for f in bf}

    def test_merged_lines_warn(self):
        codes = self._findings(
            "Deg One — Inst — 2001 — GPA 3.0\n"
            "Deg Two, Inst — 2002 — GPA 4.0\n")
        self.assertIn("education-merged", codes)

    def test_unstructured_warn(self):
        codes = self._findings("Deg One, Inst, 2001, GPA 3.0\n")
        self.assertIn("education-unstructured", codes)


class TestShapeAndAliases(unittest.TestCase):
    def test_wrong_format_fails_loudly(self):
        from builder.parser import parse_text
        from builder.cuts import find_cuts
        from builder.lint import lint
        doc = parse_text("## CUT 2 - Some Job\n\n**Org - X - 2020**\n"
                         "- a bullet\n", source="t")
        cuts, cf = find_cuts(doc)
        codes = {f.code for f in lint(doc, cuts) + cf}
        self.assertIn("no-recognized-sections", codes)

    def test_section_aliases(self):
        from builder.context import section_role
        self.assertEqual(section_role("Project Experience"), "projects")
        self.assertEqual(section_role("Work Experience"), "jobs")
        self.assertEqual(section_role("Technical Skills"), "skills")
        self.assertEqual(section_role("Publications & Awards"),
                         "publications")


class TestLooseNormalizer(unittest.TestCase):
    def test_loose_roundtrip(self):
        import sys
        from pathlib import Path as P
        sys.path.insert(0, str(P("tools").resolve()))
        from normalize import normalize
        from builder.parser import parse_text
        from builder.cuts import find_cuts
        from builder.lint import lint
        from builder.context import build_context
        from builder.findings import has_errors
        loose = P("tests/fixtures/loose_sample.txt").read_text()
        strict, log = normalize(loose)
        doc = parse_text(strict, source="loose")
        cuts, cf = find_cuts(doc)
        self.assertFalse(has_errors(lint(doc, cuts) + cf), strict)
        ctx, bf = build_context(doc, cuts)
        self.assertEqual(ctx["jobs"][0]["org"], "Acme Corp")
        self.assertEqual(ctx["jobs"][0]["title"], "Data Analyst")
        self.assertEqual(len(ctx["jobs"][0]["bullets"]), 2)
        self.assertTrue(ctx["education"][0]["structured"])
        self.assertEqual(ctx["skills"][0]["label"], "Data & technical")
        self.assertEqual(len(ctx["skills"]), 2)
        self.assertEqual(len(ctx["publications"]), 1)


if __name__ == "__main__":
    unittest.main()
