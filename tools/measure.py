"""M4 measure tool (sandbox side): render every cut × spacing and count
pages. Uses the preview renderer + LibreOffice, and swaps the theme font
to Carlito (metric stand-in for Aptos, which isn't installed here) so
counts approximate real Word output. The owner-side equivalent — real
Word, real Aptos, and the enforcement gate — is tools/Check-Pages.ps1.

Usage: python tools/measure.py MASTER TEMPLATE [CUT ...]
       (no cuts given = measure all)
"""

import io
import json
import subprocess
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from builder.parser import parse_text            # noqa: E402
from builder.cuts import find_cuts               # noqa: E402
from builder.lint import lint                    # noqa: E402
from builder.context import build_context        # noqa: E402
from builder.findings import has_errors          # noqa: E402
from builder.render import apply_spacing         # noqa: E402
import preview_render                            # noqa: E402

SOFFICE = "/mnt/skills/public/docx/scripts/office/soffice.py"


def _carlito(src: Path) -> Path:
    dst = src.with_name(src.stem + ".carlito.docx")
    with zipfile.ZipFile(src) as zin, \
            zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/theme/theme1.xml":
                data = (data.replace(b"Aptos Display", b"Carlito")
                            .replace(b"Aptos", b"Carlito"))
            zout.writestr(item, data)
    return dst


def _pages(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[-1])
    return -1


def main(master, template, *cut_names):
    doc = parse_text(Path(master).read_text(encoding="utf-8"), source=master)
    cuts, cfind = find_cuts(doc)
    findings = lint(doc, cuts) + cfind
    if has_errors(findings):
        for f in findings:
            print(f.format())
        raise SystemExit("errors present — fix the master first")
    names = list(cut_names) or sorted(cuts, key=lambda n: (n != "default", n))
    print("(sandbox fonts are metric-compatible stand-ins; owner-side "
          "Check-Pages.ps1 in real Word is the gate)")
    print(f"{'cut':<12} {'spacing':<8} pages")
    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        for name in names:
            ctx, bfind = build_context(doc, cuts, name)
            if has_errors(bfind):
                for f in bfind:
                    print(f.format())
                print(f"{name:<12} {'—':<8} skipped (build errors)")
                continue
            cj = td / f"{name}.json"
            cj.write_text(json.dumps(ctx, ensure_ascii=False),
                          encoding="utf-8")
            for spacing in ("airy", "tight"):
                outdocx = td / f"{name}.{spacing}.docx"
                with redirect_stdout(io.StringIO()):
                    preview_render.main(str(template), str(cj), str(outdocx))
                apply_spacing(outdocx, spacing)
                cdoc = _carlito(outdocx)
                subprocess.run([sys.executable, SOFFICE, "--headless",
                                "--convert-to", "pdf", "--outdir", str(td),
                                str(cdoc)], capture_output=True)
                print(f"{name:<12} {spacing:<8} "
                      f"{_pages(cdoc.with_suffix('.pdf'))}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
