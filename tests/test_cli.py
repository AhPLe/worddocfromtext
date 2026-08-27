import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from builder.cli import main

FIX = str(Path(__file__).parent / "fixtures" / "mini_master.md")


class TestCli(unittest.TestCase):
    def test_check_mode_exit_zero_on_warnings_only(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main([FIX, "--check"])
        self.assertEqual(rc, 0)
        self.assertIn("0 error(s)", out.getvalue())

    def test_json_mode_stdout_is_pure_json(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main([FIX, "--json", "--cut", "analyst"])
        self.assertEqual(rc, 0)
        ctx = json.loads(out.getvalue())   # would fail on any stray line
        self.assertEqual(ctx["meta"]["cut"], "analyst")
        self.assertEqual(len(ctx["jobs"][0]["bullets"]), 3)

    def test_list_cuts_default_first(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main([FIX, "--list-cuts"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().split(), ["default", "analyst"])

    def test_unknown_cut_is_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = main([FIX, "--json", "--cut", "nope"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
