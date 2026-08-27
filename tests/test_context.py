import json
import unittest
from pathlib import Path

from builder.parser import parse_text
from builder.cuts import find_cuts
from builder.context import build_context, rescan_for_slots, SlotLeakError

FIX = Path(__file__).parent / "fixtures" / "mini_master.md"

EMPTY_ENTRY = (
    "## Projects\n"
    "\n"
    "### Ghost — 2019\n"
    "- ⟦placeholder only⟧\n"
)


class TestContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = parse_text(FIX.read_text(encoding="utf-8"), source=str(FIX))
        cls.cuts, _ = find_cuts(cls.doc)

    def test_default_cut_content(self):
        ctx, _ = build_context(self.doc, self.cuts, "default")
        self.assertEqual(len(ctx["jobs"]), 2)
        acme = ctx["jobs"][0]
        self.assertEqual(acme["org_line"],
                         "Acme Corp — Springfield, ST\tJan 2020–Present")
        self.assertEqual(acme["title"], "Senior Widget Analyst")
        self.assertEqual(acme["bullets"], [
            "Did a measurable thing with widgets; improved throughput.",
            "Rebuilt the reporting pipeline across two teams.",
            "Shipped a dashboard used weekly.",
        ])
        self.assertEqual(
            ctx["summary"],
            "Data person with sample experience and a sample publication.")
        self.assertEqual(acme["location"], "Springfield, ST")
        self.assertEqual(len(ctx["education"]), 2)
        ms, bs = ctx["education"]
        self.assertEqual(ms, {"degree": "M.S., Sampleology",
                              "institution": "Sample University",
                              "dates": "2015–2016", "gpa": "3.9",
                              "structured": True})
        self.assertFalse(bs["structured"])
        self.assertTrue(bs["degree"].startswith("B.S., Examples"))
        self.assertEqual(len(ctx["skills"]), 2)
        self.assertEqual(ctx["skills"][0],
                         {"label": "Technical",
                          "text": "Python, SQL, Docker, Git"})
        self.assertEqual(len(ctx["publications"]), 1)
        self.assertEqual(ctx["extras"], [])

    def test_no_slot_markers_and_no_nonshipping_content(self):
        ctx, _ = build_context(self.doc, self.cuts, "default")
        blob = json.dumps(ctx, ensure_ascii=False)
        self.assertNotIn("\u27e6", blob)
        self.assertNotIn("\u27e7", blob)
        self.assertNotIn("Never ships", blob)          # hooks section
        self.assertNotIn("SUMMARY SLOT", blob)          # slot content
        self.assertNotIn("verify metric", blob)         # inline slot content
        self.assertNotIn("Analyst person", blob)        # unselected variant
        self.assertNotIn("leadership", blob)            # default-off bullet

    def test_named_cut_full_features(self):
        ctx, _ = build_context(self.doc, self.cuts, "analyst")
        self.assertEqual(len(ctx["jobs"]), 1)          # beta entry excluded
        acme = ctx["jobs"][0]
        self.assertEqual(acme["title"], "Widget Data Analyst")
        self.assertEqual(acme["bullets"], [
            "Did a measurable thing with widgets; improved throughput.",
            "Shipped a dashboard used weekly.",
            "Presented findings to leadership quarterly.",  # re-enabled
        ])
        self.assertEqual(ctx["summary"],
                         "Analyst person focused on widgets and reports.")

    def test_entry_with_only_slot_bullets_is_dropped(self):
        doc = parse_text(EMPTY_ENTRY)
        cuts, _ = find_cuts(doc)
        ctx, findings = build_context(doc, cuts, "default")
        self.assertEqual(ctx["projects"], [])
        self.assertIn("entry-empty", {f.code for f in findings})

    def test_rescan_raises_on_leak(self):
        with self.assertRaises(SlotLeakError):
            rescan_for_slots({"x": "bad \u27e6slot\u27e7 content"})


if __name__ == "__main__":
    unittest.main()
