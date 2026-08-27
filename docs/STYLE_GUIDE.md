# STYLE_GUIDE.md — input format for resume-docx-builder

Paste-ready spec for any thread or person producing master files or
standalone cut files for this pipeline. Files that follow this guide
render to formatted one-page .docx; files that don't now fail loudly
at `--check` instead of rendering an empty page.

The golden rule: **structure is machinery.** The words are yours; the
skeleton below is the parser's. Check any file with:
`python -m builder FILE.md --check`

## File skeleton (exact shapes)

```markdown
# Any title line (required, ignored by the renderer)

## Header
Name · phone · email · GitHub: url
LinkedIn: url · City, ST

## Summary
One paragraph of plain text. (Optional extra paragraphs tagged
<!-- id: summary-x --> are variants a cut can select; they never
ship unselected.)

## Professional experience
### Organization — City, ST — Mon YYYY–Mon YYYY
**Job Title**
- One bullet, one rendered line; two related clauses joined by a
  semicolon is the deliberate density pattern; never chain three.
- Another bullet.

## Education
**DEGREE** — INSTITUTION — DATES — GPA X.XX

## Projects
### Project name — Mon YYYY–Present
- Bullet.

## Skills
**Data & technical:** Python, SQL, R, ...
**Materials science:** FTIR, NMR, ...

## Publications & awards
- Citation line.
- Award line, Mon YYYY.
```

## Hard rules (each one has broken a real render)

1. **Sections are `##` headings.** Recognized (case-insensitive, with
   aliases): Header/Contact; Summary; Professional experience / Work
   experience / Experience / Employment; Education; Projects / Project
   experience / Personal projects; Skills / Technical skills / Core
   competencies; Publications / Awards. A file with none of the core
   sections is rejected (`no-recognized-sections`).
2. **Entries are `###` headings, never bold paragraphs.**
   `**Company — city, State — Aug 2022–Present**` as a paragraph renders
   NOTHING; it must be `### Company — city, State — Aug 2022–Present`.
   Parts are separated by SPACED EM DASHES (` — `): last part = dates
   (right-aligned on the page), first = organization, middle =
   location. Dates go in a ` — ` part, not in parentheses.
3. **The title line** is a lone `**Bold Title**` paragraph immediately
   under the `###` line.
4. **Education lines**: `**DEGREE** — INSTITUTION — DATES — GPA X.XX`,
   one line each, each starting with `**` (or blank-line separated).
   Merged or comma-separated lines render flat and ugly
   (`education-merged` / `education-unstructured` WARNs).
5. **Skills lines** are labeled blocks: `**Label:** item, item, ...`
   — bold label ending with a colon. An unbolded "Data & technical:
   ..." line is NOT a skills entry.
6. **Bullets** start `- `. Blank lines separate paragraphs; a line
   starting `**` also starts a new paragraph.
7. **Slots `⟦ ... ⟧`** gate unresolved content: nothing inside ever
   ships, and a slot must open and close within one paragraph. Any
   ERROR blocks rendering entirely — there is no --force.
8. **HTML comments `<!-- ... -->` never ship.** Use them for notes,
   banners, posting analysis. `<!-- id: kebab-name -->` trailing a
   line names that block/entry for cut maps; `<!-- id: name off -->`
   = ships only when a cut includes it.
9. **Cut maps** live in a ```` ```yaml ```` block: `cut: name`,
   single-line `exclude: [id, id]` / `include: [id]` lists (the
   mini-YAML does not fold wrapped lists), `title_overrides:` map,
   `summary: variant-id`.
10. **Standalone cut files are just small masters.** Same grammar,
    all sections present, rendered with the default cut:
    `python -m builder CUT.md --render --template template.docx --out cut.docx`
    Decorative banners (`====`) and NOTE blocks go inside `<!-- -->`.

## Common breakages (from a real file, Jul 2026)

| What was written                          | Symptom                    | Fix |
|-------------------------------------------|----------------------------|-----|
| No `##` sections, `====` banners           | empty .docx ("nothing")   | add `##` sections; banner → comment |
| `**Org — Loc — Dates**` bold paragraph     | entry ignored              | `### Org — Loc — Dates` |
| `**Summary.** text...` inline label        | not the summary            | `## Summary` heading, plain paragraph |
| `**jobtracker (May 2026–Present)**`        | no date column             | `### jobtracker — May 2026–Present` |
| `Data & technical: ...` unbolded           | skills line dropped        | `**Data & technical:** ...` |
| Publication paragraphs w/o `- `            | fine (paragraphs allowed in Publications) — bullets preferred for consistency | |
| Education line with commas / merged lines  | flat line, no columns      | rule 4 |

## What renders where

Header lines → static in the template today (see roadmap). Summary →
single block under Summary. Jobs/Projects → org line with
right-aligned dates, italic title/location line, bullets. Education →
four tab-aligned columns. Skills → label-bold lines. Publications →
bullets. Page style: single-spaced, bullets packed, 6pt after each
group; the one-page gate is `.\tools\Check-Pages.ps1 FILE.docx`.

## Loose mode (experimental alternate front door, Jul 2026)

A hand-typed file with NO markup can be converted to strict grammar:

```
Jordan Sample
jordan@example.com | jsample.github.io | Springfield, ST
Professional Experience
Acme Corp - Springfield, ST - Jan 2020-Present
Data Analyst
- A bullet.
Technical Skills
Data & technical: SQL, Python, R
```

`python tools/normalize.py LOOSE.txt STRICT.md` recognizes plain
section names (via the same aliases), promotes `Org - Loc - Dates`
lines to `###` entries (hyphen or em-dash separators; last part must
look like dates), bolds titles and `Label:` skills lines and education
degrees, and prints every decision it made. Wording is never changed;
contact-line separators (| or commas) are preserved exactly as typed.
Then check and render the strict file normally.

For the header to render from the FILE (any user, not the static
name), use the dynamic template: name = first header line, centered
big; each remaining header line = a centered contact line; emails,
github.io, and linkedin.com text become real hyperlinks at render
time (works with the static template too).
`python tools/dynamize_template.py template.docx template_dynamic.docx`
rebuilds it from any template version. Known wart: section headings
are static in the template, so an empty section still shows its
heading — give every section content or use a template variant.

## Roadmap (remaining)

- **Bold-entry recovery** in strict mode: treat `**A — B — C**`
  paragraphs inside jobs/projects as entries (WARN, not silence) —
  loose mode already handles them via normalize.
- **Conditional section headings** in the template (hide empty
  sections).
