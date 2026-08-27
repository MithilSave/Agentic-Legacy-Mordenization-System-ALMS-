# Martínez Saucedo, Rodríguez, Gomes Rocha, Pereira dos Santos — "Migration of Monolithic Systems to Microservices: A Systematic Mapping Study", Information and Software Technology, Vol. 177, 2025, art. 107590

**bib key:** `martinez2025mapping` — text-only reference (#2 in the supplied list).
**⚠️ Claude has NOT read this paper.** Fill the bracketed items from the PDF.

---

## Role in the ALMS paper
Background citation providing a **recent, high-venue (IST) mapping** of the research
landscape. Use it to:
- give the field's structure (a mapping study classifies rather than synthesises):
  what inputs, techniques, outputs, validation methods, and tool support have been
  studied, and where the gaps are;
- **locate ALMS on that map** — and, crucially, argue the specific cell ALMS occupies
  (fully-local LLM + graph clustering + deployable containerised output + HITL,
  evaluated on a laptop) is thinly populated or empty.

## To extract from the PDF (fill these)
- **Number of studies mapped**, time span, venues.
- **Classification dimensions / facets** used (e.g. decomposition input type,
  technique, granularity, evaluation strategy, degree of automation, tool
  availability). Reproduce the facet names — ALMS's Related Work table columns should
  echo them.
- **Distribution of studies across facets** — e.g. "X% use static analysis, Y%
  dynamic, Z% ML/LLM", "most evaluations are single-case / lab", "few produce
  runnable output". Each such statistic is a citable gap statement for ALMS.
- **Explicitly stated research gaps / recommendations for future work.**
- **Coverage of LLM-based approaches** — how many, how recent; whether any are
  fully-local or low-resource (likely none → ALMS's niche).
- **Languages studied** — confirm the field is Java-dominant and Python is
  under-represented.

## Citable sentences (fill after reading)
- Intro / Background (field is active but fragmented): "[quote]"
- Related work (facet placement of ALMS): "[paraphrase of the facets]"
- Gap statement 1 — few approaches produce deployable artefacts: "[quote/stat]"
- Gap statement 2 — evaluations are small-scale / lab-only (licenses ALMS's N=1
  framing as consistent with the field, while still a limitation): "[quote/stat]"
- Gap statement 3 — LLM approaches assume hosted/large models: "[quote/stat]"

## BibTeX — in paper/refs.bib (Elsevier IST; add DOI, e.g.
`10.1016/j.infsof.2024.107590`; verify year — article number 107590 suggests a 2024
online-first / 2025 issue).
