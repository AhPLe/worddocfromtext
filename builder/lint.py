"""Lint: document-level checks. Combines the parser's own findings
(unbalanced markers, unclosed comments/fences) with structural checks.

Slot-related and style checks are skipped inside non-shipping sections
(cut map, interview hooks, letter rules) — those sections intentionally
hold slots and prose that never reach the page, so flagging them is
noise. Marker BALANCE errors are file-wide invariants and are reported
regardless (they come from the parser, section-agnostic by design).
"""

from .findings import Finding, ERROR, WARN, INFO
from .parser import iter_blocks, collect_ids
from .context import section_role

# A shippable bullet ending in one of these reads as unfinished.
_DANGLING = (";", ",", ":", "—", "-")


def lint(doc, cuts=None, max_bullet_len=100):
    findings = list(doc.findings)

    # Bullet ids must be unique document-wide (cut maps reference them).
    seen = {}
    for bid, line in collect_ids(doc):
        if bid in seen:
            findings.append(Finding(ERROR, "id-duplicate", line,
                                    f"bullet id '{bid}' already used at line "
                                    f"{seen[bid]}"))
        else:
            seen[bid] = line

    for ln, bid in doc.orphan_ids:
        findings.append(Finding(WARN, "id-orphan", ln,
                                f"id/entry comment '{bid}' does not trail a "
                                "bullet, paragraph, labeled line, or entry "
                                "heading"))

    for sec, _ent, blk in iter_blocks(doc):
        if section_role(sec.heading) == "non_shipping":
            continue
        if blk.kind == "bullet":
            if blk.slot_only:
                findings.append(Finding(INFO, "bullet-slot-only", blk.line,
                                        "slot-only bullet — excluded from "
                                        "output until resolved"))
            elif blk.slots:
                findings.append(Finding(WARN, "bullet-mixed", blk.line,
                                        "bullet mixes text and slot content; "
                                        "text ships, slot is dropped — resolve "
                                        "before submission"))
            if blk.text and len(blk.text) > max_bullet_len:
                findings.append(Finding(WARN, "bullet-length", blk.line,
                                        f"bullet is {len(blk.text)} chars "
                                        f"(> {max_bullet_len}); may wrap past "
                                        "one docx line — rendered page count "
                                        "is the ground truth"))
            if blk.text and blk.text.endswith(_DANGLING):
                findings.append(Finding(WARN, "bullet-dangling", blk.line,
                                        f"bullet ends with '{blk.text[-1]}' — "
                                        "looks unfinished"))
        elif blk.kind in ("paragraph", "labeled"):
            if blk.slot_only:
                findings.append(Finding(INFO, "paragraph-slot-only", blk.line,
                                        "slot-only paragraph — never ships"))
            elif blk.slots:
                findings.append(Finding(WARN, "paragraph-mixed", blk.line,
                                        "paragraph mixes text and slot "
                                        "content; text ships, slot is dropped"))
            if blk.text.count("GPA") >= 2:
                findings.append(Finding(WARN, "paragraph-two-gpa", blk.line,
                                        "one paragraph mentions GPA twice — "
                                        "credential lines merged: start each "
                                        "with a '**bold**' opening or insert "
                                        "a blank line between them"))

    # Experience entries carry a bold title line; projects don't have to.
    for sec in doc.sections:
        if section_role(sec.heading) == "jobs":
            for ent in sec.entries:
                if not ent.title:
                    findings.append(Finding(WARN, "entry-missing-title",
                                            ent.line,
                                            "experience entry has no bold "
                                            "title line"))

    # A resume file with none of the core sections is almost certainly
    # in the wrong format entirely (e.g. bold paragraphs instead of
    # ### entries, or no ## headings at all) — fail LOUDLY instead of
    # rendering an empty page.
    roles = {section_role(sec.heading) for sec in doc.sections}
    if not (roles & {"header", "summary", "jobs", "projects",
                     "education"}):
        findings.append(Finding(
            ERROR, "no-recognized-sections", 1,
            "no recognized sections found (## Header / Summary / "
            "Professional experience / Education / Projects ...) — "
            "this file doesn't follow the master grammar and would "
            "render an empty document; see docs/STYLE_GUIDE.md"))

    # Cut maps may only reference ids that exist.
    if cuts:
        known = set(seen)
        entry_ids = {ent.entry_id for sec in doc.sections
                     for ent in sec.entries if ent.entry_id}
        summary_ids = {blk.block_id for sec in doc.sections
                       if section_role(sec.heading) == "summary"
                       for blk in sec.blocks
                       if blk.kind == "paragraph" and blk.block_id}
        blocks_by_id = {blk.block_id: blk
                        for _s, _e, blk in iter_blocks(doc) if blk.block_id}
        for spec in cuts.values():
            if not spec.get("line"):
                continue  # the unconfigured built-in default
            cname = spec.get("name")
            for key in ("exclude", "include"):
                for bid in spec.get(key, ()):
                    if bid not in known:
                        findings.append(Finding(
                            ERROR, "cut-unknown-id", spec.get("line", 0),
                            f"cut '{cname}' {key}s unknown id '{bid}'"))
            for bid in spec.get("include", ()):
                blk = blocks_by_id.get(bid)
                if blk is None:
                    continue  # entry id or unknown (reported above)
                if blk.slot_only:
                    findings.append(Finding(
                        WARN, "include-slot-only", spec.get("line", 0),
                        f"cut '{cname}' includes '{bid}', a slot-only "
                        "block — nothing ships until the slot is "
                        "resolved"))
                elif not blk.off:
                    findings.append(Finding(
                        WARN, "include-noop", spec.get("line", 0),
                        f"cut '{cname}' includes '{bid}', which is not "
                        "marked off — it already ships by default"))
            for k in spec.get("title_overrides", {}):
                if k not in entry_ids:
                    findings.append(Finding(
                        ERROR, "cut-unknown-entry", spec.get("line", 0),
                        f"cut '{cname}' overrides the title of unknown "
                        f"entry '{k}' (tag the ### line with "
                        f"<!-- id: {k} -->)"))
            sel = spec.get("summary")
            if sel and sel not in summary_ids:
                findings.append(Finding(
                    ERROR, "cut-unknown-summary", spec.get("line", 0),
                    f"cut '{cname}' selects summary '{sel}', but no summary "
                    "paragraph carries that id"))
    return findings
