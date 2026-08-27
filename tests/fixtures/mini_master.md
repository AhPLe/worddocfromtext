# Sample master

<!-- guidance comment: never ships -->

## Header
Jane Q. Sample · (555) 555-0100 · jane@example.com

## Summary — swap slot
⟦SUMMARY SLOT — default version:⟧
Data person with sample experience and a sample publication.

Analyst person focused on widgets and reports. <!-- id: summary-analyst -->

## Professional experience

### Acme Corp — Springfield, ST — Jan 2020–Present <!-- id: acme -->
**Senior Widget Analyst**
- Did a measurable thing with widgets; improved throughput. <!-- id: acme-widgets -->
- Rebuilt the reporting pipeline
  across two teams. <!-- id: acme-pipeline -->
- ⟦DRAFT — needs numbers before shipping⟧
- Shipped a dashboard ⟦verify metric⟧ used weekly.
- Presented findings to leadership quarterly. <!-- id: acme-leadership off -->

### Beta LLC — Elsewhere, ST — 2018–2020 <!-- id: beta -->
- Bullet without a title line above.

## Education
**M.S., Sampleology** — Sample University — 2015–2016 — GPA 3.9

**B.S., Examples** — Example State, 2012

## Skills
**Technical:** Python, SQL,
Docker, Git
**Domain:** Widgets, Reports

## Publications & awards
- Sample, J.; "A Sample Paper" Sample Journal, 2020.

## Cut map

```yaml
cut: analyst
exclude: [acme-pipeline, beta]  # drop the pipeline bullet and Beta LLC
include: [acme-leadership]
title_overrides:
  acme: "Widget Data Analyst"
summary: summary-analyst
```

## Interview-script hooks (not page content)
- Never ships anywhere.
