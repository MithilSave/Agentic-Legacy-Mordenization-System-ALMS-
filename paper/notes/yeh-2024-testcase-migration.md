# Yeh, Ma, Chen — "Test Case Migration from Monolith to Microservices Using Large Language Models", 2024 IEEE International Conference on e-Business Engineering (ICEBE), 2024, pp. 29–35

**bib key:** `yeh2024testmigration` — text-only reference (#4 in the supplied list).
**⚠️ Claude has NOT read this paper.** Fill the bracketed items from the PDF.

---

## Role in the ALMS paper
Related-work citation for the **test-migration sub-problem**, which ALMS's **Test-Gen
agent + ShadowTestingEngine** also address. Positions ALMS as covering an end of the
pipeline (post-decomposition test generation / parity checking) that most
decomposition papers (MonoEmbed, Mono2Micro) ignore, and that Mono2Sls only touches
via a consistency validator rather than executable tests.

## To extract from the PDF (fill these)
- **Exact problem framing:** does it *translate* existing monolith test cases to the
  new service boundaries, or *generate* fresh tests? What test level (unit /
  integration / API / E2E)?
- **LLM(s) used** (model, hosted vs local), prompt strategy, any retrieval.
- **Pipeline:** inputs (monolith tests + new service structure?), outputs (per-service
  test suites?), how service boundaries are assumed/obtained.
- **Evaluation:** subject systems, how many, metrics (test pass rate, coverage,
  compilation success, fault-detection, manual-effort reduction), headline numbers.
- **Limitations** they state (flaky tests, missing fixtures, cross-service setup,
  data dependencies).

## How ALMS relates (refine after reading)
- ALMS's Test-Gen agent generates `pytest` + `hypothesis` suites per generated
  FastAPI service, plus **shadow tests** that run identical inputs through the legacy
  callable and the new callable for exact-match parity. Whether this overlaps or
  complements Yeh et al. depends on whether they translate vs generate — determine
  from the PDF.
- Both use LLMs for the test side of migration; ALMS's differentiator is **local
  model + parity-oriented shadow testing integrated into one pipeline** rather than a
  standalone test-migration step.

## Citable sentences (fill after reading)
- Related work (test migration is its own hard sub-problem): "[quote]"
- Related work (what LLMs can/can't do for test migration): "[quote]"
- Discussion / future work (shared limitation — cross-service fixtures / data): "[quote]"

## BibTeX — in paper/refs.bib (IEEE ICEBE 2024; add DOI once located, e.g.
`10.1109/ICEBEXXXXX.2024.00011`; confirm pages 29–35).
