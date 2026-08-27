# Kickoff — resume master → .docx builder

You are starting **resume-docx-builder**: a small tool that turns a canonical
markdown "master document" résumé into formatted, one-page .docx cuts. It is a
NEW project — related to, but deliberately separate from, jobtracker.

## The problem, in the owner's own workflow terms

The résumé lives twice today: a markdown master (canonical CONTENT, dense with
HTML-comment guidance and slot markers) and a Word master (the FORMATTING /
submission artifact). Content changes flow master → docx by hand, governed by a
"DOCX SYNC LIST" convention: every canon-changing session ends with an
old-line → new-line list so the Word file can be updated in minutes, and before
any submission the docx is diffed against the markdown at known regression
spots.

**This tool's entire job is to delete that convention.** The markdown master
stays canonical; the .docx becomes a *build artifact* — regenerated, never
hand-synced. Content edits stay in text (diffable, LLM-friendly, versionable);
formatting lives in exactly one Word template.

## Relationship to jobtracker — settled, do not relitigate

- **Separate repo, separate Claude Project, separate threads.** The immediate
  need is file → file with zero infrastructure friction (no Docker, no auth),
  usable within a month, iterated fast.
- **Layered so it folds into jobtracker later.** jobtracker's snippet system
  Checkpoint C (assembly + docx export + builder page) is specified but
  unbuilt. This project's core becomes that checkpoint's engine. Enforce the
  seam from day one:
  - `parser/` + `lint/` + `cuts/` = **pure Python, stdlib only** where
    possible, no I/O assumptions, fully unit-testable. These later drop into
    jobtracker as a service module unchanged.
  - `render/` = the only docx-dependent edge (docxtpl).
  - `cli.py` wraps the layers for local use.
- The stable interchange boundary is the **render context**: a plain
  JSON-serializable dict produced by parse+cut-selection. Tests, the CLI, and
  the future jobtracker endpoint all sit on that boundary.

## Master format spec v1 (formalizing conventions that already exist)

The real master already follows these rules informally; the tool makes them
enforceable. Examples below are sanitized — the real master contains personal
contact data (see PII note at bottom).

1. **HTML comments `<!-- ... -->`** — guidance for the human/LLM maintaining
   the master (tailoring rules, claim-verification warnings, variant notes).
   Stripped on parse; NEVER ships. No semantic subtypes needed in v1.
2. **Slot markers `⟦ ... ⟧`** — unresolved content requiring the owner's
   input. Two hard rules:
   - **Lint: markers must balance.** (Evidence this earns its keep: the live
     master, as pasted in July 2026, contains at least one unbalanced `⟧` in
     the header block.) Report line numbers.
   - **Build: slot content never ships.** If the selected cut still contains
     any `⟦...⟧` after variant resolution, the build HARD-FAILS listing each
     offending line. There is no --force. A résumé with a stray
     `⟦TABLE-CHECK...⟧` in it is a catastrophic ship; the tool exists to make
     it impossible.
3. **Structure grammar** (matches the current master):
   - `## Section` — top-level sections (Header, Summary, Professional
     experience, Skills, Publications & awards, Cut map).
   - `### Org — City, ST — DateRange` — an experience entry.
   - A `**bolded**` line directly under it — the title line.
   - `- ` bullets — one docx line each is the *target* (see lint 5).
   - Plain paragraphs — flowing text (summary, citations).
   - Skills lines: `**Label:** comma, separated, list`.
4. **Bullet IDs** — a bullet the cut map references carries a trailing
   comment: `- Consolidated five... <!-- id: usda-crossgrain -->`. Explicit
   IDs, not positions: reordering the master must never silently change a
   cut. Lint: duplicate IDs; cut-map references to unknown IDs.
5. **One-line-per-bullet lint** — approximate by character count against a
   template-measured constant (calibrate once by eye: find the longest bullet
   that still fits one line in the rendered template; that length is the warn
   threshold). This is a WARNING; the page-count check (below) is ground
   truth. The density idiom to preserve: two related clauses joined by a
   semicolon, each independently true; never three.
6. **Cut map grammar** — a `## Cut map` section at the bottom; one fenced
   YAML block per cut:

   ```yaml
   cut: analyst
   title_overrides:
     usda: "Data Analyst (Postgraduate Research Appointment)"
   summary: summary-analyst          # id of the summary variant to use
   exclude: [usda-error-rewrite]     # bullet ids dropped in this cut
   include: []                       # bullet ids that are default-off, on here
   ```

   The **default cut** = every non-slot bullet, default title lines, default
   summary. v1 keeps the grammar to exactly these keys; extend only when a
   real cut needs more. Variant blocks (alternate summaries, alternate
   titles) live in the master as slot-marked or id-tagged blocks the cut map
   selects — settle the exact representation in the first design session
   *against the real master*, not hypothetically.

## Pipeline

parse → lint → select cut → render context (JSON) → docxtpl render →
page-verify (optional) → `cuts/<master-stem>.<cut>.docx`

CLI shape:

```
python -m builder master.md --cut analyst --out cuts/
python -m builder master.md --check            # lint only, no render
python -m builder master.md --list-cuts
python -m builder master.md --cut analyst --json   # dump the render context
```

Fail loud, with line numbers, on: unbalanced markers, slot leakage into the
selected cut, unknown/duplicate ids, a cut map that isn't valid YAML.

## Template creation guide (the direct ask)

The template is a **.docx owned and edited in Word** — formatting changes
never require code changes. That ownership model is why docxtpl over
building documents programmatically.

1. **Start from the current Word master** — its formatting is already
   approved. Save a copy as `template.docx`.
2. **Hollow it out**: delete content until ONE exemplar of each element
   remains — one section heading, one org line, one title line, one bullet,
   one skills line, one citation paragraph.
3. **Replace exemplar text with Jinja tags.** Inline values: `{{ name }}`,
   `{{ job.org_line }}`. Repetition: docxtpl's paragraph-scoped block tags —
   `{%p for job in jobs %}` ... `{%p endfor %}` — which remove the tag's own
   paragraph from the output. ⚠ VERIFY the exact block-tag syntax against the
   docxtpl docs in your environment before relying on it; do not build from
   memory of it.
4. **Tags inherit the paragraph's style.** A `{{ b }}` sitting in a
   Bullet-styled paragraph renders every bullet in that style. This is the
   whole mechanism — keep named styles (SectionHead, OrgLine, TitleLine,
   Bullet, Body) rather than direct formatting, so Word-side tweaks apply
   globally.
5. **Right-aligned dates**: a right tab stop at the text margin, defined in
   the OrgLine/citation paragraph style; the context supplies
   `"Org — City, ST\tAug 2022–Present"` with a literal tab. (Publications
   convention: authors `;`-separated including after the final author;
   "Title" without a trailing period; journal; year-only for academic cuts,
   month+year for industry cuts — the cut map can carry a date-format flag
   when that variant is first needed.)
6. **v1 renders bullets as plain text** (the master's bullets are plain). If
   inline bold/italic is ever needed, docxtpl's RichText is the tool — defer
   until a real bullet needs it.
7. **Acceptance test for M2**: render the default cut and put it next to the
   hand-maintained docx. "Matches within eyeball tolerance" is the bar.

## Page-count verification (the one-page rule, automated where possible)

If LibreOffice is available (it is in Claude's environment; check locally):
convert the rendered docx headlessly to PDF and count pages (`pdfinfo`, or
`pdftoppm` and count images); >1 page = build failure with the bullet-length
report attached. Where LibreOffice isn't available, the lint heuristics warn
and the human eyeballs — say which level of verification each build got.

## Environment notes for this project's threads

- **Check availability before assuming**: in the July 2026 jobtracker sandbox,
  `python-docx` was importable, `docxtpl` was NOT, and there is no network for
  pip. If docxtpl is absent in your session: develop and execution-verify the
  pure layers (parser, lint, cuts, context) in-sandbox, deliver the render
  layer syntax-checked for local execution, and SAY SO — the
  "execution-verified vs. parse-checked" honesty rule carries over from
  jobtracker's CLAUDE.md.
- Claude's built-in docx skill generates documents via docx-js (npm). That is
  fine for one-off documents but is NOT this tool: the builder must be a
  program the owner runs locally against a Word-owned template. Don't drift
  to docx-js for the builder itself.
- The owner's machine: Windows + PowerShell. Commands PowerShell-compatible;
  no `&&` chaining, no bash heredocs.

## jobtracker integration surface (for the LATER phase — pinned from the
## actual codebase, July 2026; re-verify before wiring)

Base: FastAPI backend; Bearer access token + rotating SINGLE-USE refresh
tokens (a refresh consumes the token and returns a new pair — clients must
single-flight refreshes).

- `POST /auth/register`, `POST /auth/login` → TokenPair; `POST /auth/refresh`
  (rotating); `GET /auth/me`.
- `POST /resumes/upload` — file upload, **content-hash deduplicated** per
  user (re-uploading identical content returns the existing row rather than a
  duplicate). `POST /resumes/text` for text-sourced resumes. `GET /resumes`,
  `GET /resumes/with-usage`, `GET /resumes/{id}/download`.
- `POST /applications` and the job-postings upsert both accept `resume_id` —
  attaching a generated cut to the application it was built for.
- `GET /snippets`, `POST /snippets`, `PATCH /snippets/{id}`,
  `POST /snippets/{id}/set-default`, `DELETE /snippets/{id}` — the versioned
  snippet store (content edits append versions; metadata edits mutate;
  default follows lineage). Relevant when master content migrates from file
  to DB (Checkpoint C), not before.

Integration sketch (M5, parked): builder renders a cut → `POST
/resumes/upload` → link the returned `resume_id` on the application → the
"which resume worked" analysis closes the loop. The dedup means rebuilding an
unchanged cut is idempotent.

## Milestones (vertical slices; discussion before building each)

- **M1** — parser + linter, execution-verified against the REAL master
  (including the currently-unbalanced marker as a test case). Output: the
  JSON render context for the default cut.
- **M2** — template hollowed from the Word master + default-cut render that
  matches the hand-built docx by eye. This is the moment the SYNC LIST
  convention dies.
- **M3** — cut map + variants (analyst cut first; it's the one with a real
  title override).
- **M4** — page-count automation where LibreOffice exists.
- **M5 (parked)** — jobtracker service wiring per the surface above.

## Working style (carried over from jobtracker's CLAUDE.md)

Be honest and direct when the owner is wrong; explain the purpose behind
better options so the logic can be checked; state assumptions (reversible →
proceed and note; irreversible → ask). Discussion before building. Minimal
diffs. Say what was execution-verified vs. parse-checked. If unsure of a
third-party API detail (docxtpl especially), say so and mark it for
verification rather than inventing it.

**PII note**: the master document contains real contact information. Keep it
out of pasted chat text when a sanitized excerpt serves; if this repo is ever
public-facing portfolio material, the real master stays out of it (template +
a fictional sample master ship instead).
