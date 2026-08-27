"""Loose-mode normalizer (experimental alternate front door).

Converts a hand-typed resume — no ## marks, plain section names,
unbolded skills labels, plain org lines — into strict master markdown
for the existing pipeline, and prints every structural decision it
made. Wording is never changed; separators the user typed in contact
lines (| or commas) are preserved verbatim.

Usage: python tools/normalize.py LOOSE.txt STRICT.md
Then:  python -m builder STRICT.md --check
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from builder.context import section_role  # noqa: E402

_DATEY = re.compile(r"(19|20)\d\d|present", re.I)
_LABEL = re.compile(r"^([^:]{2,48}):\s+(.+)$")
_SEPS = (" \u2014 ", " \u2013 ", " - ")


def _as_section(line):
    s = line.strip().lstrip("#").strip()
    if not s or len(s) > 48 or s.startswith("-") or ":" in s:
        return None
    role = section_role(s)
    return (s, role) if role != "extra" else None


def _entry_parts(line):
    s = line.strip().strip("*").strip()
    for sep in _SEPS:
        if sep in s:
            parts = [p.strip() for p in s.split(sep) if p.strip()]
            if len(parts) >= 2 and _DATEY.search(parts[-1]):
                return parts
    return None


def normalize(text):
    out, log = [], []
    role = None
    header, expect_title = [], False
    lines = text.splitlines()
    i = 0
    # header phase: everything before the first recognized section
    while i < len(lines):
        sec = _as_section(lines[i])
        if sec:
            break
        if lines[i].strip():
            header.append(lines[i].strip())
        i += 1
    name = header[0] if header else "Unknown"
    out.append(f"# {name} \u2014 resume (normalized)")
    out.append("")
    out.append("## Header")
    for j, hl in enumerate(header):
        out.append(hl)
        out.append("")  # blank line: each header line = own paragraph
    log.append(f"header: name={name!r}, {len(header)-1} contact line(s), "
               "separators preserved as typed")

    for line in lines[i:]:
        if line.strip().startswith("\u2022"):
            line = line.replace("\u2022", "-", 1)
        sec = _as_section(line)
        if sec:
            s, role = sec
            out.extend(["", f"## {s}", ""])
            log.append(f"section: {s!r} -> {role}")
            expect_title = False
            continue
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if stripped.startswith("-"):
            out.append(line)
            expect_title = False
            continue
        if role in ("jobs", "projects"):
            parts = _entry_parts(line)
            if parts:
                out.extend(["", "### " + " \u2014 ".join(parts)])
                log.append(f"entry: {parts[0]!r} ({len(parts)} parts)")
                expect_title = role == "jobs"
                continue
            if expect_title and len(stripped) < 70:
                out.append(f"**{stripped.strip('*')}**")
                log.append(f"title bolded: {stripped!r}")
                expect_title = False
                continue
            out.append(line)
        elif role == "skills":
            m = _LABEL.match(stripped)
            if m and not stripped.startswith("**"):
                out.append(f"**{m.group(1)}:** {m.group(2)}")
                log.append(f"skills label bolded: {m.group(1)!r}")
            else:
                out.append(line)
        elif role == "education":
            parts = None
            for sep in _SEPS:
                p = [x.strip() for x in stripped.split(sep) if x.strip()]
                if len(p) >= 3:
                    parts = p
                    break
            if parts:
                if not parts[0].startswith("**"):
                    parts[0] = f"**{parts[0].strip('*')}**"
                    log.append(f"education degree bolded: {parts[0]!r}")
                out.append(" \u2014 ".join(parts))
                out.append("")
            else:
                out.append(line)
        else:
            out.append(line)
    txt = "\n".join(out)
    txt = re.sub(r"\n{3,}", "\n\n", txt) + "\n"
    return txt, log


def main(src, dst):
    text = Path(src).read_text(encoding="utf-8")
    strict, log = normalize(text)
    Path(dst).write_text(strict, encoding="utf-8")
    for entry in log:
        print("  " + entry)
    print(f"wrote {dst} \u2014 now run: python -m builder {dst} --check")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
