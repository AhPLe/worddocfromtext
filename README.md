# resume-docx-builder

Converts the canonical markdown résumé master (`RESUME_MASTER.md`) into a
JSON render context (M1, done) and from there into formatted one-page
`.docx` cuts (M2, next). Stdlib-only through the context layer; `docxtpl`
enters only at the render edge.

## Status

- **M1 — parser / linter / render context: DONE** (execution-verified:
  24 unit tests + full run against the real master).
- **M2 — template + render: DONE** (Jul 2026). `template.docx` was
  derived from Al's hand-formatted Word master by
  `tools/hollow_template.py`; rendering verified in-sandbox via a
  docxtpl-equivalent Jinja pass (`tools/preview_render.py`) with a
  visual PDF check under Aptos-metric fonts. `builder/render.py`
  (the docxtpl production path) is parse-checked only — docxtpl cannot
  be installed in the sandbox — and is verified locally (below).
- **M3 — cut variants: DONE** (Jul 2026). Full cut grammar applied
  (default-off via `<!-- id: x off -->` at the block);
  the analyst cut is defined in the master's cut-map section and
  execution-verified end to end (26 tests + rendered preview).
- **M4 — page-count automation: DONE** (Jul 2026): sandbox measure
  table + owner-side Word COM gate + the `--spacing` render knob.
  M5 — jobtracker wiring (parked).

## Usage (PowerShell)

```powershell
cd resume-docx-builder

# Lint the master; exit 1 if any ERROR:
python -m builder ..\RESUME_MASTER.md --check

# Emit the render context (REFUSES while any ERROR exists; no --force):
python -m builder ..\RESUME_MASTER.md --json --out context.json

# List cuts (from fenced yaml blocks in the cut-map section):
python -m builder ..\RESUME_MASTER.md --list-cuts

# Run the test suite:
python -m unittest

# Render a .docx (M2; requires: pip install docxtpl):
python -m builder ..\RESUME_MASTER.md --render --template template.docx --out cut.docx
```

## M2: rendering and the template

- Same strict gate: any ERROR refuses to render; no `--force`.
- **First local run verification:** `pip install docxtpl`, render, open
  the docx. Canary #1: the Novelis "R&T Center" line renders (proves
  autoescape handled `&`). Canary #2: education shows four aligned
  columns. Rendered page count is the ground truth for length.
- **Template knobs** (edit `template.docx` in Word; formatting only —
  content always comes from the master):
  - Margins: Layout > Margins. Right-aligned tab columns (dates, GPA)
    follow automatically — `render.py` re-glues right tab stops to the
    right margin after every render.
  - Bullet spacing: the List Paragraph style (currently 6pt after).
    Tick "Don't add space between paragraphs of the same style" on that
    style for tight bullet groups (saves ~2" on a full render).
  - Font: one knob — Design > Fonts or the Normal style (run-level
    font overrides were stripped; theme font is Aptos).
  - Block formatting: each repeating structure is ONE prototype block
    in the template; restyle it and every rendered copy follows.
- Header (name + contact + hyperlinks) is static in the template — it
  never varies per cut; edit it directly in Word.
- Education master grammar (v2): `DEGREE — INSTITUTION — DATES —
  GPA X.XX` per line; non-matching lines render flat with an INFO.
- Schema change vs the M1 zip: skills entries are
  `{label, text}` (was `items` — a Jinja dict-method collision found
  and fixed during M2 verification).
- Publications render as flat citation bullets in v1; the bold
  right-tabbed date column needs a master date-field grammar (M3).
- `tools/hollow_template.py` re-derives the template if the Word
  master is reformatted; `tools/preview_render.py` is the sandbox
  verification renderer (not the production path).

If console output garbles the `⟦ ⟧ · —` characters, set
`$env:PYTHONUTF8 = "1"` first (the CLI also reconfigures its own streams
to UTF-8 where the console allows it).

## Format spec v1 — constraints on the master

These are deliberate strictness on whichever LLM (or human) writes the
master. The parser is lenient — every violation becomes a line-numbered
finding in one `--check` pass — but the build gate is strict: any ERROR
blocks `--json` (and, in M2, rendering). There is no `--force`.

1. **Slot markers `⟦ ⟧` must balance**, and a slot must open and close
   within one block (one bullet / one paragraph). A column-0 structure
   line (`- `, `## `, `### `, ```` ``` ````) inside a slot splits the
   block and surfaces as unbalanced-marker ERRORs. Nothing inside `⟦ ⟧`
   ever ships; a slot-only bullet or paragraph is excluded entirely; a
   mixed bullet ships its text and WARNs until resolved.
2. **Separate paragraphs need a blank line between them.** Two idioms
   are recognized without one: a non-bullet line starting with `**`
   begins a new paragraph (Education), and a line that is pure slot
   content closing with `⟧` stands alone (the SUMMARY SLOT label).
3. **HTML comments `<!-- -->` are guidance and never ship.** A trailing
   `<!-- id: kebab-case -->` names its bullet for cut maps; ids must be
   unique document-wide.
4. **Structure grammar:** `##` sections; `###` entries split on the
   spaced em dash `" — "` (org — middle… — dates); a fully-bold first
   line under an entry is its title; `**Label:** items` lines are
   labeled (Skills) blocks. Inline `**bold**` is stripped to plain text
   in v1 (RichText deferred to M2+).
5. **Cut blocks** are fenced yaml in the cut-map section; keys:
   `cut`, `exclude`, `include`, `title_overrides`, `summary` (lists are
   single-line `[a, b]` — the mini-YAML does not fold wrapped lists).
   M3 semantics (settled Jul 2026):
   - One flat id namespace, unique document-wide: any block (bullet,
     paragraph, labeled line) takes a trailing `<!-- id: x -->`; the
     same comment on a `###` heading line names the ENTRY. Excluding an
     entry id drops the whole entry.
   - `<!-- id: x off -->` marks a block **default-off**: it ships only
     when a cut `include`-s it. Default-off-ness is marked at the block
     in the master (the content source of truth), not in cut-map
     config — this settles the kickoff's open design question. Slot
     rules are unchanged and stronger: slot content never ships,
     included or not. There is no configurable `cut: default` block.
   - `title_overrides: {entry_id: "Title"}` swaps an entry title.
   - Summary variants are extra Summary-section paragraphs tagged
     `<!-- id: summary-x -->`; a cut's `summary: summary-x` selects
     one. Id-less paragraphs are the default summary; unselected
     variants never ship. Education ignores cuts (canon: never drops).
   - The linter validates every reference: `cut-unknown-id` /
     `cut-unknown-entry` / `cut-unknown-summary` and `summary-empty`
     (selected variant still slot-gated) are ERRORs; `include-noop`
     (target not marked off) and `include-slot-only` are WARNs.
   - Analyst-cut page findings (Carlito ≈ Aptos metrics): 2 pages as
     rendered; with the tight-bullets style knob only Publications
     (~4 lines) spills — closable via top/bottom margins 1.0"→0.75"
     and/or canon's Scigenesis trim. Automating that loop is M4.
6. Non-shipping sections (headings containing "cut map",
   "Interview-script hooks", "Letter & prose") are parsed and marker-
   checked but never reach the render context and skip style lints.

## Layout

```
builder/           parser.py  lint.py  cuts.py  context.py  cli.py  findings.py
tests/             unit tests + tests/fixtures/mini_master.md (sanitized, no PII)
docs/              resume-docx-builder-kickoff.md (governing spec)
```

The stable boundary between layers is the JSON render context; M2's
template consumes it and nothing deeper. Bullet one-line length warns at
100 chars — a placeholder until calibrated against the real template
(rendered page count is the ground truth).


## Loose mode (experimental)

`tools/normalize.py` converts a hand-typed, markup-free resume into
strict master markdown (decision log printed); `tools/
dynamize_template.py` builds `template_dynamic.docx` whose header
renders from the file (name + contact lines, centered, emails/GitHub/
LinkedIn auto-linked). See docs/STYLE_GUIDE.md, "Loose mode". The
render context now also carries `header.name` and
`header.contact_lines` (schema addition, 0.4.0).

## Editing the template (syntax cheatsheet)

`template.docx` is a docxtpl template: your formatting + Jinja tags.
Everything except the static header (name/contact/links) renders from
the master via the JSON context.

- `{%p for ... %}` / `{%p endfor %}` are PARAGRAPH tags: each sits
  alone in its own paragraph, and that whole paragraph disappears at
  render. Never delete or reorder a for/endfor pair.
- Between a for/endfor sits ONE prototype block; restyle it and every
  rendered copy follows. Safe edits: fonts, sizes, bold/italic,
  spacing, tab stops, borders, margins (right-aligned tab columns
  re-glue to the right margin on every render).
- Variables by section: `{{ summary }}`; jobs — `{{ job.org }}`,
  `{{ job.dates }}`, `{{ job.title }}`, `{{ job.location }}`, bullets
  `{{ b }}`; education — `{{ e.degree }}`, `{{ e.institution }}`,
  `{{ e.gpa }}`, `{{ e.dates }}`; projects — `{{ p.org }}`,
  `{{ p.dates }}`, bullets `{{ b }}`; skills — `{{ s.label }}`,
  `{{ s.text }}`; publications — `{{ pub }}`.
- DANGER: retyping part of a tag in Word can split it across formatting
  runs and break rendering. If you touch a tag, retype the WHOLE tag in
  one go. `merge_runs` (docx skill) heals split runs;
  `tools/hollow_template.py` re-derives the template from a reformatted
  Word master (now also strips the legacy negative indents that caused
  the Jul 2026 page-edge bug).

## M4: page budget — how to count pages

The one-page constraint is load-bearing; rendered page count is the
ground truth.

- Owner-side gate (real Word, real Aptos):
  `.\tools\Check-Pages.ps1 .\analyst.docx` (add `-MaxPages 2` for the
  master-level doc). Exit 1 when over budget.
- One-command flow (one line each; PS5 has no `&&`):
  `python -m builder .\RESUME_MASTER.md --render --cut analyst --spacing tight --template .\template.docx --out .\analyst.docx`
  then `.\tools\Check-Pages.ps1 .\analyst.docx`
- `--spacing tight|airy|template`: tight packs bullet groups to single
  spacing (~1.6" reclaimed on a full render); airy = 6pt after every
  bullet; template = leave the template's own setting.
- Sandbox measure table (Claude-side): `python tools/measure.py MASTER
  TEMPLATE [CUT ...]` renders every cut × spacing and prints pages
  (Carlito ≈ Aptos metrics).
- When over budget, the levers in order: `--spacing tight`; top/bottom
  margins 1.0"→0.75" (template edit, tabs follow automatically);
  canon's content lever (Scigenesis trimmed to 2–3 bullets via the
  cut's exclude list).

### Template v2 style (Jul 2026, Al's spec — baked in)

The template now bakes the submission style: single line spacing
everywhere (docDefaults), bullets packed to single spacing within a
group, 6pt only after the LAST bullet of a group (List Paragraph:
contextualSpacing + 6pt-after), theme font Times New Roman (one knob in
Word: Design → Fonts, or theme1.xml). Plain `--render` produces this;
`--spacing airy` loosens to 6pt after every bullet; the analyst cut
fits ONE page in this style with 1.0" top/bottom margins.

### Education line grammar (submission-critical)

Each education line must match
`**DEGREE** — INSTITUTION — DATES — GPA X.XX`
with SPACED EM DASHES ( — ), and each line must start with `**` or be
separated by a blank line — otherwise adjacent lines merge into one
paragraph and render flat (raw dashes, no columns). The builder now
WARNs (`education-merged` / `education-unstructured`) when this
happens. Commas are not separators.

### M5 prep (parked)

`docs/MERGE_PROMPT.md` is a ready-to-paste Opus prompt for merging
content-thread changes into the canonical master without breaking
machinery (ids, off flags, cut maps, slots, canon regression spots).