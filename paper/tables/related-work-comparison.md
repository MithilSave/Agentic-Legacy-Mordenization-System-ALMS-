<!-- STATUS: drafted from paper/notes/*.md — verify every cell against the source PDFs before the manuscript -->

# Related-work comparison (Table 1 candidate)

"Migration" column = how far down the pipeline the system goes:
**D**ecompose → **G**enerate code → **T**est → **Deploy artifact**.

| System (year) | Input | Boundary method | Pipeline reach | Test generation | LLM(s) | Hardware / hosting | API cost | Offline | HITL | Target output | Evaluation | Reproducibility |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Mono2Micro** — Kalia et al. 2021 | Java bytecode + **runtime traces** + human use-case labels | Hierarchical spatio-temporal clustering (target `n`) | **D** | — | none | local, no LLM | — | yes | analyst reviews clusters + use-case tuples | class→service partition (explainable) | 7 JEE apps (4 OSS + 3 proprietary) + survey of 21 practitioners; metrics SM/ICP/BCP/IFN/NED | deterministic clustering; needs trace collection |
| **MonoEmbed** — Sellami & Saied 2025 | Java source, class level | **Learned** LM embeddings + **contrastive (triplet) fine-tuning (LoRA)** → clustering (Affinity Propagation) | **D** | — | 18 pre-trained encoders/LLMs benchmarked; best are 7B LM-embedding models + closed APIs | **GPU for fine-tuning**; inference CPU/GPU | model/GPU time (fine-tune once) | inference yes; training needs corpus | no | class→service partition | 8 Java monoliths vs 6 decomposition baselines; metrics CHM/CHD/BCP/ICP/NED/COV → SCORE (best: 6.061) | fine-tune reproducible w/ seed+data; base models vary |
| **Mono2Sls** — Chen et al. 2026 | Python/JS monolith source + lightweight static analysis (`analysis_report.json`) | **LLM Architect agent** over a static call/entry-point map → `blueprint.json` | **D + G + Deploy** (AWS SAM) | consistency validator only (11 cross-artifact checks); no executable test-gen | **hosted commercial / large**: Cursor (Claude Sonnet 4.5), Claude Code (Sonnet 4.6), DeepSeek-V3.2, Claude Sonnet 4.6 | orchestrator local (Windows); **inference = cloud APIs** | **per-token API cost**; 58–106 min inference/app | **no** (needs cloud LLM) | none | deployable AWS SAM app + IaC (**vendor-locked, serverless**) | 6 reverse-engineered apps (601–3,623 LoC, 76 endpoints), live AWS deploy; VPR/DSR/API-F1/E2EPR; **pass@1, variance unmeasured (stated threat)** | non-deterministic hosted models; single run |
| **Yeh et al.** 2024 (test migration) | Existing monolith tests + (assumed) service structure | — (boundaries assumed given) | **T** | LLM migrates/generates tests for microservice targets | LLM (see PDF) | see PDF | see PDF | see PDF | see PDF | migrated per-service test cases | see PDF | see PDF |
| **ALMS** (this work) | **Python** monolith source | **Deterministic**: AST call graph → builtin/stdlib filtering → **Louvain community detection** (`random_state=42`); LLM Architect only refines | **D + G + T + Deploy artifact** (containerised FastAPI + `docker-compose.yml`) | LLM Test-Gen agent → `pytest` + `hypothesis` per service **+ ShadowTestingEngine** (legacy-vs-new exact-match parity) | **local open-weight**: `qwen2.5-coder:7b` + `nomic-embed-text` via Ollama | **single CPU laptop, ~16 GB RAM, no GPU** | **$0** | **yes** | **3 approval gates** with reject→iterate cycles | portable container images + compose + generated tests + JSON reports | **1 case study** (`sample_monolith`, 6 files / 1.6 kLoC); feasibility + `py_compile`/build validity + graph-filtering effect (134→75 nodes) + cost/resource contrast | fixed clustering seed; local model; one-command `--demo`; open artifact |

## The one-sentence positioning

Every prior automated pipeline either **stops at a partition** (Mono2Micro,
MonoEmbed) or **depends on hosted commercial LLMs and vendor-specific serverless
targets** (Mono2Sls). ALMS is the first to run the **full** monolith→microservice
migration — decomposition, code generation, test generation, and a deployable
container artifact — **entirely on a commodity laptop with local open-weight models,
at zero API cost, offline, and reproducibly**, trading SOTA decomposition quality for
access and reproducibility.
