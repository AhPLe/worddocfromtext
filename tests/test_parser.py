import unittest
from pathlib import Path

from builder.parser import parse_text, iter_blocks

FIX = Path(__file__).parent / "fixtures" / "mini_master.md"


class TestParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = parse_text(FIX.read_text(encoding="utf-8"), source=str(FIX))

    def _section(self, heading):
        return next(s for s in self.doc.sections if s.heading == heading)

    def test_title_and_sections(self):
        self.assertEqual(self.doc.title, "Sample master")
        heads = [s.heading for s in self.doc.sections]
        for h in ("Header", "Summary — swap slot", "Professional experience",
                  "Education", "Skills", "Publications & awards", "Cut map"):
            self.assertIn(h, heads)

    def test_no_parse_errors_in_fixture(self):
        self.assertEqual([f for f in self.doc.findings
                          if f.severity == "ERROR"], [])

    def test_entry_structure_ids_and_slots(self):
        acme = self._section("Professional experience").entries[0]
        self.assertEqual(acme.parts,
                         ["Acme Corp", "Springfield, ST", "Jan 2020–Present"])
        self.assertEqual(acme.title, "Senior Widget Analyst")
        self.assertEqual(acme.entry_id, "acme")
        bullets = [b for b in acme.blocks if b.kind == "bullet"]
        self.assertEqual(len(bullets), 5)
        self.assertFalse(bullets[0].off)
        self.assertEqual(bullets[4].block_id, "acme-leadership")
        self.assertTrue(bullets[4].off)
        self.assertEqual(bullets[0].block_id, "acme-widgets")
        # id comment sits on a continuation line — must still attach.
        self.assertEqual(bullets[1].block_id, "acme-pipeline")
        self.assertEqual(bullets[1].text,
                         "Rebuilt the reporting pipeline across two teams.")
        self.assertTrue(bullets[2].slot_only)
        self.assertTrue(bullets[3].slots)
        self.assertEqual(bullets[3].text,
                         "Shipped a dashboard used weekly.")

    def test_comments_never_reach_blocks(self):
        for _s, _e, blk in iter_blocks(self.doc):
            self.assertNotIn("<!--", blk.raw)
            self.assertNotIn("-->", blk.raw)

    def test_education_bold_starts_new_paragraph(self):
        edu = self._section("Education")
        paras = [b for b in edu.blocks if b.kind == "paragraph"]
        self.assertEqual(len(paras), 2)
        self.assertTrue(paras[0].text.startswith("M.S., Sampleology"))
        self.assertTrue(paras[1].text.startswith("B.S., Examples"))
        for p in paras:
            self.assertNotIn("**", p.text)  # v1 ships plain text

    def test_skills_labeled_with_continuation(self):
        skl = self._section("Skills")
        labeled = [b for b in skl.blocks if b.kind == "labeled"]
        self.assertEqual([b.label for b in labeled], ["Technical", "Domain"])
        self.assertEqual(labeled[0].text, "Python, SQL, Docker, Git")

    def test_summary_slot_label_stands_alone(self):
        summ = self._section("Summary — swap slot")
        self.assertTrue(summ.blocks[0].slot_only)
        self.assertEqual(
            summ.blocks[1].text,
            "Data person with sample experience and a sample publication.")
        self.assertEqual(summ.blocks[2].block_id, "summary-analyst")

    def test_cut_map_code_block_captured(self):
        cm = self._section("Cut map")
        codes = [b for b in cm.blocks if b.kind == "code"]
        self.assertEqual(len(codes), 1)
        self.assertEqual(codes[0].lang, "yaml")
        self.assertIn("cut: analyst", codes[0].text)


if __name__ == "__main__":
    unittest.main()
