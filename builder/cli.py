"""CLI. Modes:
  --check      lint only (default); findings to stdout; exit 1 on errors
  --json       emit render context (stdout or --out); findings to stderr;
               REFUSES output while any ERROR exists (no --force, by design)
  --list-cuts  print available cut names, 'default' first

Exit codes: 0 clean, 1 findings contain errors (or slot leak), 2 usage/IO.
"""

import argparse
import json
import sys
from pathlib import Path

from .findings import has_errors, sorted_findings, summarize
from .parser import parse_text
from .cuts import find_cuts
from .lint import lint
from .context import build_context, SlotLeakError


def _utf8_console():
    """Windows consoles often default to a legacy code page; the master is
    full of ⟦⟧/·/— so reconfigure defensively (no-op where unsupported)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
            if enc != "utf8":
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main(argv=None):
    _utf8_console()
    ap = argparse.ArgumentParser(
        prog="python -m builder",
        description="resume-docx-builder — parse/lint a résumé master and "
                    "emit the JSON render context (M1: no docx render yet).")
    ap.add_argument("master", help="path to the master .md file")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="lint only and report findings (default mode)")
    mode.add_argument("--json", action="store_true",
                      help="emit the render context as JSON")
    mode.add_argument("--list-cuts", action="store_true",
                      help="list available cuts")
    mode.add_argument("--render", action="store_true",
                      help="render a .docx from the template "
                           "(requires docxtpl installed locally)")
    ap.add_argument("--cut", default="default", help="cut to build")
    ap.add_argument("--template", default="template.docx",
                    help="template .docx for --render")
    ap.add_argument("--spacing", choices=("template", "tight", "airy"),
                    default="template",
                    help="bullet spacing for --render: 'tight' packs "
                         "bullet groups to single spacing (one-page "
                         "lever), 'airy' spaces every bullet 6pt, "
                         "'template' leaves the template's setting")
    ap.add_argument("--out", default="",
                    help="output path (--json: JSON file; "
                         "--render: .docx; default <master>.<cut>.docx)")
    ap.add_argument("--max-bullet-len", type=int, default=100,
                    help="one-docx-line warn threshold in characters "
                         "(placeholder until calibrated against the "
                         "template in M2)")
    args = ap.parse_args(argv)

    path = Path(args.master)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    doc = parse_text(text, source=str(path))
    cuts, cut_findings = find_cuts(doc)

    if args.list_cuts:
        for name in sorted(cuts, key=lambda n: (n != "default", n)):
            print(name)
        return 0

    if args.cut not in cuts:
        print(f"unknown cut '{args.cut}'; available: " + ", ".join(sorted(cuts)),
              file=sys.stderr)
        return 2

    findings = lint(doc, cuts, max_bullet_len=args.max_bullet_len)
    findings.extend(cut_findings)

    context = None
    try:
        context, build_findings = build_context(doc, cuts, args.cut)
        findings.extend(build_findings)
    except SlotLeakError as exc:
        print(f"FATAL slot leak: {exc}", file=sys.stderr)
        return 1

    # In --json mode, stdout stays pure JSON (pipeable); findings go to
    # stderr. In check mode the findings ARE the output.
    report = sys.stderr if args.json else sys.stdout
    if args.render:
        report = sys.stderr
    for f in sorted_findings(findings):
        print(f.format(), file=report)
    print(summarize(findings), file=report)

    if has_errors(findings):
        if args.json or args.render:
            print("errors present — refusing to emit output "
                  "(no --force exists by design)", file=sys.stderr)
        return 1

    if args.render:
        tpl = Path(args.template)
        if not tpl.exists():
            print(f"template not found: {tpl}", file=sys.stderr)
            return 2
        out = Path(args.out) if args.out else Path(
            f"{path.stem}.{args.cut}.docx")
        from .render import render_docx  # lazy: docxtpl only needed here
        try:
            render_docx(context, tpl, out, spacing=args.spacing)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"wrote {out}", file=sys.stderr)
        return 0

    if args.json:
        blob = json.dumps(context, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(blob + "\n", encoding="utf-8")
            print(f"wrote {args.out}", file=sys.stderr)
        else:
            print(blob)
    return 0
