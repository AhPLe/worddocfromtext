"""Parser for the résumé master format (spec v1).

Lenient by design: malformed input never raises — every problem becomes
a Finding with a line number. Strictness is enforced downstream: the
build gate refuses to emit a render context while any ERROR exists, so
lenient character-dropping here can never leak unresolved content.

Pipeline within this module:
  1. Strip HTML comments (guidance; NEVER ships), capturing `id:` tags.
  2. Line-oriented structure parse into Sections / Entries / Blocks.
  3. Per-block slot extraction: ⟦...⟧ content is pulled out; the
     remainder is the block's "shippable" text.

Format constraints this parser enforces (welcome strictness on the
LLM that writes the master — see README):
  - Separate flowing paragraphs need a blank line between them. Two
    convenience rules soften this: a non-bullet line starting with
    '**' begins a new paragraph (the Education idiom), and a paragraph
    that is pure slot content and closes its slot at end-of-line stands
    alone (the "SUMMARY SLOT label" idiom).
  - A slot must open and close within one block; a column-0 structure
    line ('- ', '## ', '### ', '```') inside a slot will split it and
    surface as unbalanced-marker ERRORs.
"""

import re
from dataclasses import dataclass, field

from .findings import Finding, ERROR, WARN

SLOT_OPEN = "\u27e6"   # ⟦  U+27E6 mathematical left white square bracket
SLOT_CLOSE = "\u27e7"  # ⟧  U+27E7

_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_ID_RE = re.compile(r"^\s*id:\s*([A-Za-z0-9][A-Za-z0-9_-]*)(\s+off)?\s*$")
_H1_RE = re.compile(r"^#\s+(.*)$")
_H2_RE = re.compile(r"^##\s+(.*)$")
_H3_RE = re.compile(r"^###\s+(.*)$")
_TITLE_RE = re.compile(r"^\*\*([^*].*?)\*\*\s*$")
_LABELED_RE = re.compile(r"^\*\*([^*:]+):\*\*\s*(.*)$")
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_FENCE_RE = re.compile(r"^```(\w*)\s*$")


def normalize_ws(s: str) -> str:
    return " ".join(s.split())


@dataclass
class Slot:
    text: str
    line: int


@dataclass
class Block:
    kind: str                 # "bullet" | "paragraph" | "labeled" | "code"
    line: int                 # first source line of the block's content
    raw: str                  # comment-stripped, slots still embedded
    text: str = ""            # shippable: slots removed, '**' stripped, ws normalized
    label: str = ""           # labeled blocks only
    lang: str = ""            # code blocks only
    block_id: str = ""        # from a trailing <!-- id: ... -->
    off: bool = False         # <!-- id: ... off --> = default-off: ships
                              # only when a cut include-s it
    slots: list = field(default_factory=list)

    @property
    def slot_only(self) -> bool:
        return bool(self.slots) and not self.text


@dataclass
class Entry:
    heading: str              # shippable heading text
    line: int
    parts: list               # heading split on " — " (spaced em dash)
    entry_id: str = ""        # from a trailing <!-- id: ... --> on the ### line
    title: str = ""
    title_line: int = 0
    blocks: list = field(default_factory=list)


@dataclass
class Section:
    heading: str
    line: int
    blocks: list = field(default_factory=list)   # blocks before any entry
    entries: list = field(default_factory=list)


@dataclass
class Document:
    source: str
    title: str = ""
    sections: list = field(default_factory=list)
    preamble: list = field(default_factory=list)  # blocks before first '##'
    comments: list = field(default_factory=list)  # (line, stripped body)
    orphan_ids: list = field(default_factory=list)  # (line, id) not on a bullet
    findings: list = field(default_factory=list)


def _strip_comments(text):
    """Remove HTML comments, preserving line numbers (newline-for-newline).

    Returns (stripped_text, comments, ids_by_line, findings). id comments
    are attributed to the line the comment STARTS on, so a trailing
    `<!-- id: x -->` lands on its bullet line even mid-continuation.
    """
    comments, ids_by_line, findings = [], {}, []

    def _sub(m):
        line = text.count("\n", 0, m.start()) + 1
        body = m.group(1)
        comments.append((line, body.strip()))
        idm = _ID_RE.match(body)
        if idm:
            ids_by_line[line] = (idm.group(1), bool(idm.group(2)))
        return "\n" * m.group(0).count("\n")

    stripped = _COMMENT_RE.sub(_sub, text)
    pos = stripped.find("<!--")
    if pos != -1:
        line = stripped.count("\n", 0, pos) + 1
        findings.append(Finding(ERROR, "comment-unclosed", line,
                                "'<!--' without a matching '-->'"))
    return stripped, comments, ids_by_line, findings


def scan_slots(raw, base_line, findings):
    """Extract ⟦...⟧ spans from a block. Returns (shippable_text, slots).

    Stray '⟧' and unclosed '⟦' each add an ERROR Finding. An unclosed
    slot swallows everything to end-of-block INTO the slot — so even in
    the malformed case, marked content can never reach shippable text.
    The build gate makes these errors fatal before anything is emitted.
    """
    out, slots = [], []
    depth, buf, open_line = 0, [], 0
    line = base_line
    for ch in raw:
        if ch == "\n":
            line += 1
        if ch == SLOT_OPEN:
            if depth == 0:
                open_line = line
                buf = []
            else:
                findings.append(Finding(ERROR, "slot-nested", line,
                                        "nested '⟦' inside an open slot"))
            depth += 1
        elif ch == SLOT_CLOSE:
            if depth == 0:
                findings.append(Finding(ERROR, "slot-stray-close", line,
                                        "'⟧' with no matching '⟦'"))
            else:
                depth -= 1
                if depth == 0:
                    slots.append(Slot(normalize_ws("".join(buf)), open_line))
        else:
            (buf if depth else out).append(ch)
    if depth:
        findings.append(Finding(ERROR, "slot-unclosed", open_line,
                                "'⟦' never closed with '⟧'"))
        slots.append(Slot(normalize_ws("".join(buf)), open_line))
    return "".join(out), slots


def parse_text(text: str, source: str = "<memory>") -> Document:
    stripped, comments, ids_by_line, cfindings = _strip_comments(text)
    doc = Document(source=source, comments=comments)
    doc.findings.extend(cfindings)
    consumed = set()

    cur_section = None
    cur_entry = None
    acc = None  # {"kind", "start", "parts", "label"?, "lang"?}

    def target():
        if cur_entry is not None:
            return cur_entry.blocks
        if cur_section is not None:
            return cur_section.blocks
        return doc.preamble

    def flush():
        nonlocal acc
        if acc is None:
            return
        a, acc = acc, None
        raw = "\n".join(a["parts"])
        if a["kind"] == "code":
            target().append(Block(kind="code", line=a["start"], raw=raw,
                                  text=raw, lang=a.get("lang", "")))
            return
        shippable, slots = scan_slots(raw, a["start"], doc.findings)
        if shippable.count("**") % 2:
            doc.findings.append(Finding(WARN, "bold-unpaired", a["start"],
                                        "odd number of '**' markers in block"))
        # v1 ships plain text: inline bold markers are stripped (RichText
        # is deferred until a real bullet needs it — kickoff §template 6).
        blk = Block(kind=a["kind"], line=a["start"], raw=raw,
                    text=normalize_ws(shippable.replace("**", "")),
                    label=a.get("label", ""), slots=slots)
        if a["kind"] in ("bullet", "paragraph", "labeled"):
            end = a["start"] + len(a["parts"]) - 1
            for ln in range(a["start"], end + 1):
                info = ids_by_line.get(ln)
                if info is None or ln in consumed:
                    continue
                bid, off = info
                if blk.block_id:
                    doc.findings.append(Finding(
                        WARN, "id-multiple", ln,
                        f"block already has id '{blk.block_id}'; "
                        f"ignoring '{bid}'"))
                else:
                    blk.block_id = bid
                    blk.off = off
                consumed.add(ln)
        target().append(blk)

    for idx, line in enumerate(stripped.split("\n"), start=1):
        # Inside a fence: consume verbatim until the closing fence.
        if acc is not None and acc["kind"] == "code":
            if _FENCE_RE.match(line):
                flush()
            else:
                acc["parts"].append(line)
            continue

        fm = _FENCE_RE.match(line)
        if fm:
            flush()
            # content starts on the NEXT line; store that as block.line so
            # per-line findings inside cut blocks point at real lines.
            acc = {"kind": "code", "start": idx + 1, "parts": [],
                   "lang": fm.group(1)}
            continue

        if not line.strip():
            flush()
            continue

        m = _H1_RE.match(line)
        if m:
            flush()
            if not doc.title:
                doc.title = normalize_ws(m.group(1))
            continue

        m = _H2_RE.match(line)
        if m:
            flush()
            cur_entry = None
            heading, _ = scan_slots(m.group(1), idx, doc.findings)
            cur_section = Section(heading=normalize_ws(heading), line=idx)
            doc.sections.append(cur_section)
            continue

        m = _H3_RE.match(line)
        if m:
            flush()
            if cur_section is None:
                doc.findings.append(Finding(WARN, "entry-before-section", idx,
                                            "'###' entry before any '##' section"))
                cur_section = Section(heading="(implicit)", line=idx)
                doc.sections.append(cur_section)
            heading, _ = scan_slots(m.group(1), idx, doc.findings)
            heading = normalize_ws(heading)
            parts = [p.strip() for p in heading.split(" — ") if p.strip()]
            cur_entry = Entry(heading=heading, line=idx, parts=parts)
            info = ids_by_line.get(idx)
            if info is not None:
                cur_entry.entry_id = info[0]
                if info[1]:
                    doc.findings.append(Finding(
                        WARN, "id-entry-off-ignored", idx,
                        "'off' has no meaning on an entry id; ignored"))
                consumed.add(idx)
            cur_section.entries.append(cur_entry)
            continue

        # Title line: the first content line directly under a fresh entry,
        # entirely bold and not a '**Label:**' line.
        if (cur_entry is not None and not cur_entry.title
                and not cur_entry.blocks and acc is None):
            tm = _TITLE_RE.match(line)
            if tm and not _LABELED_RE.match(line):
                t, _ = scan_slots(tm.group(1), idx, doc.findings)
                cur_entry.title = normalize_ws(t)
                cur_entry.title_line = idx
                continue

        bm = _BULLET_RE.match(line)
        if bm:
            flush()
            acc = {"kind": "bullet", "start": idx,
                   "parts": [bm.group(1).rstrip()]}
            continue

        lm = _LABELED_RE.match(line)
        if lm:
            flush()
            acc = {"kind": "labeled", "start": idx,
                   "label": lm.group(1).strip(),
                   "parts": [lm.group(2).rstrip()]}
            continue

        # Education idiom: a non-bullet line opening with '**' starts a new
        # paragraph even without a preceding blank line.
        if line.lstrip().startswith("**") and (acc is None
                                               or acc["kind"] != "bullet"):
            flush()
            acc = {"kind": "paragraph", "start": idx, "parts": [line.strip()]}
        elif acc is not None:
            acc["parts"].append(line.strip())
        else:
            acc = {"kind": "paragraph", "start": idx, "parts": [line.strip()]}

        # Summary-slot-label idiom: a paragraph that is (so far) pure slot
        # content and just closed its slot at end-of-line stands alone.
        if acc["kind"] == "paragraph" and line.rstrip().endswith(SLOT_CLOSE):
            scratch = []
            shippable, _ = scan_slots("\n".join(acc["parts"]),
                                      acc["start"], scratch)
            if not scratch and not shippable.replace("**", "").strip():
                flush()

    if acc is not None and acc["kind"] == "code":
        doc.findings.append(Finding(ERROR, "fence-unclosed", acc["start"] - 1,
                                    "code fence '```' never closed"))
    flush()

    doc.orphan_ids = [(ln, info[0])
                      for ln, info in sorted(ids_by_line.items())
                      if ln not in consumed]
    return doc


def iter_blocks(doc):
    """Yield (section, entry_or_None, block) across the whole document."""
    for sec in doc.sections:
        for blk in sec.blocks:
            yield sec, None, blk
        for ent in sec.entries:
            for blk in ent.blocks:
                yield sec, ent, blk


def collect_ids(doc):
    """All (id, line) pairs in document order (duplicates included).

    One flat namespace: block ids (bullets, paragraphs, labeled lines)
    AND entry ids — cut maps reference any of them interchangeably.
    """
    out = [(blk.block_id, blk.line) for _s, _e, blk in iter_blocks(doc)
           if blk.kind in ("bullet", "paragraph", "labeled")
           and blk.block_id]
    for sec in doc.sections:
        for ent in sec.entries:
            if ent.entry_id:
                out.append((ent.entry_id, ent.line))
    return sorted(out, key=lambda x: x[1])
