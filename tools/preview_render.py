"""Preview renderer — sandbox verification aid, NOT the production path.

Replicates docxtpl's documented transform (a paragraph containing a
{%p ... %} tag is replaced by the bare {% ... %} tag) and renders
word/document.xml with plain Jinja2 against a context JSON. Values are
XML-escaped before rendering, mirroring render_docx's autoescape=True.

Used in Claude's sandbox, where docxtpl cannot be installed, to produce
a viewable .docx/.pdf and visually verify the template. The production
path is builder/render.py + docxtpl on the owner's machine.

Usage: python tools/preview_render.py template.docx context.json out.docx
"""

import json
import re
import sys
import zipfile
from xml.sax.saxutils import escape

import jinja2

_PTAG = re.compile(
    r"<w:p\b[^>]*>(?:(?!</w:p>).)*?\{%p\s+(.*?)\s*%\}(?:(?!</w:p>).)*?</w:p>",
    re.S)


def _esc(o):
    if isinstance(o, str):
        return escape(o)
    if isinstance(o, list):
        return [_esc(x) for x in o]
    if isinstance(o, dict):
        return {k: _esc(v) for k, v in o.items()}
    return o


def main(template, context_json, out, spacing=None):
    ctx = _esc(json.load(open(context_json, encoding="utf-8")))
    with zipfile.ZipFile(template) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = _PTAG.sub(lambda m: "{% " + m.group(1) + " %}", xml)
    rendered = jinja2.Template(xml).render(**ctx)
    with zipfile.ZipFile(template) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = rendered.encode("utf-8")
            zout.writestr(item, data)
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    if spacing:
        from builder.render import apply_spacing
        apply_spacing(out, spacing)
    from builder.render import linkify_header
    linkify_header(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
