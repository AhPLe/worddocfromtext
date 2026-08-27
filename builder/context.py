"""Render-context builder: Document -> plain dict, the stable boundary
between parsing and templating (the template consumes it, nothing deeper).

Cut semantics (M3, settled Jul 2026):
  - exclude: ids removed by this cut (blocks OR whole entries).
  - off (grammar: <!-- id: name off -->): default-off, marked AT the
    block in the master — ships only when a cut include-s it. This is
    the answer to the kickoff's open design question; chosen over a
    configurable default-cut exclude list for locality (the master is
    the content source of truth, so default-off-ness lives next to the
    content). Reversible: one find/replace migrates the grammar.
  - include: turns default-off blocks on.
  - title_overrides: {entry-id: "New Title"}.
  - summary: id of a summary-section paragraph variant; id-tagged
    summary paragraphs never ship unselected.

Callers must gate on has_errors(all findings) before emitting the
context anywhere — the CLI does. rescan_for_slots is the belt-and-
braces final check: if a slot marker somehow survives into the JSON,
we raise rather than ship.
"""

import json

from .findings import Finding, ERROR, WARN, INFO
from .parser import SLOT_OPEN, SLOT_CLOSE

# Sections that exist for humans/LLMs, never for the page.
NON_SHIPPING_KEYS = ("cut map", "interview-script hooks", "letter & prose")

_ROLES = (
    ("header", "header"),
    ("contact", "header"),
    ("summary", "summary"),
    ("professional experience", "jobs"),
    ("work experience", "jobs"),
    ("employment", "jobs"),
    ("experience", "jobs"),
    ("education", "education"),
    ("personal project", "projects"),
    ("project", "projects"),
    ("technical skills", "skills"),
    ("core competencies", "skills"),
    ("skills", "skills"),
    ("publications", "publications"),
    ("awards", "publications"),
)


def section_role(heading: str) -> str:
    h = heading.lower()
    if any(k in h for k in NON_SHIPPING_KEYS):
        return "non_shipping"
    for key, role in _ROLES:
        if h.startswith(key):
            return role
    return "extra"


class SlotLeakError(RuntimeError):
    pass


def _block_ships(blk, exclude, include):
    """Cut filter shared by bullets, publications, and skills lines:
    excluded ids never ship; default-off blocks ship only when included.
    Slot content never ships regardless (checked by callers)."""
    if blk.block_id and blk.block_id in exclude:
        return False
    if blk.off and blk.block_id not in include:
        return False
    return True


def _entry_dict(entry, exclude, include):
    bullets = []
    for blk in entry.blocks:
        if blk.kind != "bullet" or blk.slot_only:
            continue
        if not _block_ships(blk, exclude, include):
            continue
        if blk.text:
            bullets.append(blk.text)
    parts = entry.parts
    if len(parts) >= 2:
        # Literal tab before the dates: the M2 template right-aligns the
        # date with a right tab stop, so the context carries the \t.
        org_line = " — ".join(parts[:-1]) + "\t" + parts[-1]
    else:
        org_line = entry.heading
    middle = parts[1:-1]
    return {
        "org": parts[0] if parts else entry.heading,
        "middle": middle,
        "location": middle[0] if middle else "",
        "dates": parts[-1] if len(parts) >= 2 else "",
        "org_line": org_line,
        "title": entry.title,
        "bullets": bullets,
    }


# Education line grammar (v2, for the docx layout's four columns):
#   DEGREE — INSTITUTION — DATES — GPA X.XX
# Lines not matching stay whole in 'degree' with structured=False; the
# template renders those flat, so an un-migrated master still builds.
def _education_entry(text):
    parts = [p.strip() for p in text.split(" — ")]
    if len(parts) == 4 and parts[3].upper().startswith("GPA"):
        return {"degree": parts[0], "institution": parts[1],
                "dates": parts[2], "gpa": parts[3][3:].strip(),
                "structured": True}
    return {"degree": text, "institution": "", "dates": "", "gpa": "",
            "structured": False}


def build_context(doc, cuts, cut_name="default"):
    """Return (context_dict, build_findings). Does NOT gate on errors —
    that is the caller's job — but does hard-fail on slot leakage."""
    findings = []
    spec = cuts[cut_name]
    exclude = set(spec.get("exclude", ()))
    include = set(spec.get("include", ()))
    title_overrides = spec.get("title_overrides", {})
    summary_id = spec.get("summary", "")

    ctx = {
        "meta": {"source": doc.source, "cut": cut_name,
                 "builder": "resume-docx-builder 0.4.0 (loose-mode prep)"},
        "header": {"lines": []},
        "summary": "",
        "jobs": [],
        "projects": [],
        "education": [],
        "skills": [],
        "publications": [],
        "extras": [],
    }

    for sec in doc.sections:
        role = section_role(sec.heading)
        if role == "non_shipping":
            continue
        if role == "header":
            for blk in sec.blocks:
                if blk.kind in ("paragraph", "labeled") and blk.text:
                    ctx["header"]["lines"].append(blk.text)
        elif role == "summary":
            if summary_id:
                for b in sec.blocks:
                    if b.kind == "paragraph" and b.block_id == summary_id:
                        if b.text:
                            ctx["summary"] = b.text
                        else:
                            findings.append(Finding(
                                ERROR, "summary-empty", b.line,
                                f"summary variant '{summary_id}' has no "
                                "shippable text (still slot-gated?)"))
                        break
                # unknown id -> lint reports cut-unknown-summary (ERROR)
            else:
                # default summary = the id-LESS shippable paragraphs;
                # id-tagged paragraphs are variants awaiting selection.
                ctx["summary"] = " ".join(
                    b.text for b in sec.blocks
                    if b.kind == "paragraph" and b.text and not b.block_id)
        elif role in ("jobs", "projects"):
            for ent in sec.entries:
                if ent.entry_id and ent.entry_id in exclude:
                    continue
                d = _entry_dict(ent, exclude, include)
                if ent.entry_id and ent.entry_id in title_overrides:
                    d["title"] = title_overrides[ent.entry_id]
                if not d["bullets"] and not d["title"]:
                    findings.append(Finding(INFO, "entry-empty", ent.line,
                                            f"entry '{d['org']}' has no shippable "
                                            f"bullets in cut '{cut_name}' and no "
                                            "title — dropped"))
                    continue
                if not d["bullets"]:
                    findings.append(Finding(INFO, "entry-no-bullets", ent.line,
                                            f"entry '{d['org']}' renders with a "
                                            f"title but no bullets in cut "
                                            f"'{cut_name}'"))
                ctx[role].append(d)
        elif role == "education":
            # canon rule: Education NEVER drops from any cut — the cut
            # filter is deliberately not applied here.
            for blk in sec.blocks:
                if blk.kind == "paragraph" and blk.text:
                    e = _education_entry(blk.text)
                    if not e["structured"]:
                        if blk.text.count("GPA") >= 2:
                            findings.append(Finding(
                                WARN, "education-merged", blk.line,
                                "looks like multiple education lines "
                                "merged into ONE paragraph — start each "
                                "line with ** (bold) or separate them "
                                "with a blank line"))
                        else:
                            findings.append(Finding(
                                WARN, "education-unstructured", blk.line,
                                "education line doesn't match 'DEGREE — "
                                "INSTITUTION — DATES — GPA X.XX' (spaced "
                                "em dashes); renders as one flat line"))
                    ctx["education"].append(e)
        elif role == "skills":
            for blk in sec.blocks:
                if (blk.kind == "labeled" and blk.text
                        and _block_ships(blk, exclude, include)):
                    # key name "text", not "items": Jinja resolves
                    # dict.items (the method) before the key — a real
                    # render-breaking collision caught in M2 preview.
                    ctx["skills"].append({"label": blk.label,
                                          "text": blk.text})
        elif role == "publications":
            for blk in sec.blocks:
                if (blk.kind in ("bullet", "paragraph") and blk.text
                        and _block_ships(blk, exclude, include)):
                    ctx["publications"].append(blk.text)
        else:  # extra
            findings.append(Finding(INFO, "section-unmapped", sec.line,
                                    f"section '{sec.heading}' has no dedicated "
                                    "role; shipped under extras"))
            ctx["extras"].append({
                "heading": sec.heading,
                "paragraphs": [b.text for b in sec.blocks
                               if b.kind == "paragraph" and b.text],
                "bullets": [b.text for b in sec.blocks
                            if b.kind == "bullet" and b.text],
            })

    hl = ctx["header"]["lines"]
    ctx["header"]["name"] = hl[0] if hl else ""
    ctx["header"]["contact_lines"] = hl[1:]

    rescan_for_slots(ctx)
    return ctx, findings


def rescan_for_slots(context):
    """Final invariant check: no slot marker may survive into the context."""
    blob = json.dumps(context, ensure_ascii=False)
    for ch in (SLOT_OPEN, SLOT_CLOSE):
        i = blob.find(ch)
        if i != -1:
            raise SlotLeakError(
                "slot marker survived into the render context near: ..."
                + blob[max(0, i - 40): i + 40] + "...")
