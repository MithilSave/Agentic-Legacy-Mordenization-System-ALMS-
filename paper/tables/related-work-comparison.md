<!-- STATUS: stub — fill during Phase 2 Task 2.9 from paper/notes/*.md -->

# Related-work comparison

Draft. Verify every cell against the source paper before using in the manuscript.

| System | Input | Boundary method | Code generation | Test generation | LLM hosting | Hardware | Cost | Offline | Human-in-loop | Target output | Eval scale |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Mono2Micro** (`kalia2021mono2micro`) | Java bytecode + runtime traces + use cases | Spatio-temporal clustering | — (partitioning only) | — | — (no LLM) | — | — | — | analyst reviews clusters | class→service partitioning | open-source + proprietary Java apps |
| **MonoEmbed** (`sellami2025monoembed`) | Monolith source components | LLM embeddings + contrastive fine-tuning (LoRA) → clustering | — | — | LLM for embeddings; fine-tuned | GPU (fine-tuning) | model + GPU time | no | no | microservice partitioning | multiple projects |
| **Mono2Sls** (`chen2026mono2sls`) | Monolith web backend source | LLM Architect agent from static call graph / entrypoints | 4 tool-using LLM agents + curated SAM KB | consistency validator (not full test gen) | commercial hosted (Cursor / Claude Code / DeepSeek-V3.2 / Claude Sonnet 4.6) | cloud | per-token API | no | no | deployable AWS SAM (serverless) app + IaC | 6 apps, >10K LOC, 76 endpoints |
| **Yeh et al.** (`yeh2024testmigration`) | Existing monolith test cases | — (assumes boundaries given) | — | LLM rewrites tests for microservice targets | LLM (hosted) | — | API | no | no | migrated test cases | case studies |
| **ALMS (this work)** | Python monolith source | Deterministic AST call graph + Louvain community detection (seed-fixed) | LLM Refactoring agent + `py_compile` retry loop + Jinja scaffolds | LLM Test-Gen agent + shadow/parity engine, `pytest` + `hypothesis` | **local Ollama** (`qwen2.5-coder:7b`) | **CPU laptop, ~16 GB** | **$0** | **yes** | **3 approval gates w/ reject-iterate** | containerised FastAPI microservices + `docker-compose.yml` + tests | 1 case study (`sample_monolith`); partner may extend |
