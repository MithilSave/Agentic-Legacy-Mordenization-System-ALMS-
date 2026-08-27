# Kalia, Xiao, Krishna, Sinha, Vukovic, Banerjee — "Mono2Micro: A Practical and Effective Tool for Decomposing Monolithic Java Applications to Microservices", ESEC/FSE 2021

**bib key:** `kalia2021mono2micro` — the canonical **non-LLM decomposition baseline**.
IBM product. Everything after it (MonoEmbed, and by extension ALMS) compares to it.

---

## Problem / claim
Modernising legacy JEE monoliths to microservices requires decomposing classes into
functionally cohesive, *explainable* groups. Prior static approaches are imprecise
(reflection, dynamic class loading, DI); dynamic approaches capture runtime deps but
still fail to align classes with **business functionality**, which is the primary
industrial concern.

## Method
**Hierarchical spatio-temporal decomposition** from runtime traces:
- **Space dimension = business use cases.** The user exercises the app UI (or runs
  functional tests) and labels each run with a use case (e.g. `Create Account`,
  `Checkout`). Probes record function entry/exit → execution traces.
- **Time dimension = runtime call traces.** Beyond *direct* call relations, Mono2Micro
  adds **indirect call relations** (long-range temporal relations) and **direct /
  indirect call patterns** capturing how classes call other classes across ≥1 use
  case.
- Build a class-class similarity `S` from these patterns; **hierarchical
  agglomerative clustering** merges the most similar clusters until a target cluster
  count `n` is reached (`n` is the only hyper-parameter; chosen non-parametrically as
  a range from N/2 downward per Scanniello et al.).
- **Explainability:** each resulting microservice is a group of classes, each mapped
  to a tuple of use cases → tells a practitioner *why* a class is where it is.

## Evaluation setup
- **7 JEE web apps** — 4 open-source (JPetStore, AcmeAir, DayTrader, PBW) + 3
  proprietary. Class coverage of traces 66–88%.
- **Baselines (4):** Bunch (software remodularisation, hill-climbing on a module
  dependency graph), FoSCI (hierarchical clustering + genetic merge), CoGCN (GCN,
  outlier-aware), MEM (minimum spanning tree). Chosen for available source + minimal
  manual input. Explicitly *excludes* ServiceCutter (needs a hand-built ERM,
  "intractable ... cannot scale past 1000 classes").
- **RQ1** partition quality via 5 metrics: **SM** (structural modularity — cohesion/
  coupling; higher better), **ICP** (inter-partition runtime call % — lower better),
  **BCP** (business context purity = avg entropy of use cases per partition — lower
  better), **IFN** (interface number), **NED** (non-extreme distribution — penalises
  tiny/huge services). **RQ2** partitioning speed. **RQ3** survey of **21 industry
  practitioners** who used the tool.

## Headline numbers / findings
- Mono2Micro **consistently strong on BCP and NED**, competitive on ICP and IFN;
  **weaker on SM** than Bunch/MEM — but those baselines' high SM comes with high NED
  (extreme size distributions), i.e. degenerate partitions.
- Faster than hill-climbing / genetic baselines (scalability for large enterprise
  apps).
- Practitioner survey: helps implement a **Strangler pattern**; recommendations are
  self-explainable; can detect unreachable code. Wanted improvements: fewer manual
  edits on top of recommendations; add **DB interactions / transaction patterns** to
  refine recommendations.

## Stated limitations / threats
Needs **runtime traces** (user must exercise use cases / have functional tests) —
coverage-limited (66–88%). JEE/Java only. No data-layer / transaction awareness.
Survey is small (21) and self-selected.

---

## How ALMS relates
- **The baseline lineage.** Mono2Micro = dynamic traces + hierarchical clustering +
  use-case labels. ALMS = **static AST call graph + Louvain** (a different clustering
  family — modularity maximisation on the graph, no target-`n`, no runtime traces, no
  human use-case labelling). Cite Mono2Micro as the established practical tool and
  position ALMS's static+Louvain choice as the trade for **zero runtime instrumentation
  and zero manual labelling** — at the cost of the business-use-case explainability
  Mono2Micro provides.
- ALMS shares Mono2Micro's stated *gap*: no data-layer / transaction modelling
  (ALMS's `tables` / `data_ownership` fields are effectively unused). Acknowledge as
  shared future work.
- **Metrics:** SM, ICP, BCP, NED are the standard partition-quality metrics; if the
  partner adds a boundary-quality evaluation, report these against a gold
  decomposition.
- Language contrast: Mono2Micro / MonoEmbed are **Java**; ALMS targets **Python** —
  worth noting the decomposition literature is Java-heavy and Python monoliths
  (Flask/Django) are under-served.

## Citable sentences
- **Intro / Background:** decomposition strategies "fall under static- or
  dynamic-analysis techniques ... apply clustering or evolutionary algorithms over
  [module] dependencies to create partitions [with] high cohesion and low coupling."
- **Background:** static analysis "suffers imprecision ... inherent to static
  analysis" (reflection, dynamic loading, DI) — but for Python + a call graph over a
  small monolith this is far less severe; note the trade honestly.
- **Related work:** Mono2Micro is an IBM product (GA Jan 2021), evaluated against
  Bunch/FoSCI/CoGCN/MEM on 7 JEE apps + a 21-practitioner survey — the reference
  point for "practical, effective" decomposition tooling.
- **Discussion:** their survey finding that users want DB/transaction patterns added
  to refine recommendations → supports ALMS listing data-ownership derivation as
  future work.

## BibTeX — in paper/refs.bib (DOI 10.1145/3468264.3473915; verify page numbers).
