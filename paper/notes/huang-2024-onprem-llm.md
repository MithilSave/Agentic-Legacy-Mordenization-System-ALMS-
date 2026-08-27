# Huang, Li, Jiang, Jiang, Liu, Sun, Liu, Liang — "A Middle Path for On-Premises LLM Deployment: Preserving Privacy Without Sacrificing Model Confidentiality" (SOLID), arXiv:2410.11182 (v3, Oct 2025)

**bib key:** `huang2024onprem` — supporting citation for the **"why deploy LLMs
locally / on-premises" motivation**. Use narrowly — its core technical contribution
is not directly about ALMS's setting.

---

## Problem / claim
Privacy-sensitive users want to run LLMs **on their own infrastructure
(on-premises)** to (1) keep private data in-house, (2) enable customization, and
(3) meet regulatory compliance. But deploying a *closed-source* model locally risks
**model theft**: adversaries can extract parameters from CPU/memory, or replicate
functionality via query-based distillation. Prior "secure only the output layer in a
TEE" approaches remain vulnerable; fully enclosing a large model in a TEE is
computationally prohibitive. Can privacy + model confidentiality coexist on-prem?

## Method (SOLID)
"Semi-Open Local Infrastructure Deployment." Theoretically identifies a **transition
layer** in deep transformers: securing the *bottom* decoder layers (before the
transition) inside a protected environment reduces distillation success far more than
securing top layers. Number of secured layers = a security↔customization trade-off.
SOLID uses a **fine-tuning-free distillation-difficulty score** to pick the minimal
set of bottom layers to secure — matching fully-secured security while keeping most
customization flexibility.

## Evaluation
5 models (1.3B–70B), 3 distillation strategies, 16 benchmarks for security, 6 tasks
for customization flexibility. Also extends query-based distillation attacks to LLMs
and shows existing on-prem frameworks "risk full functionality replication"
(confirmed on Llama2-70B).

## How ALMS relates (be precise — narrow relevance)
- **Motivation only.** SOLID's framing establishes that on-premises LLM deployment is
  a real, active need driven by **data privacy, customization, and regulatory
  compliance** — exactly the constituency ALMS targets (students, small teams,
  privacy-constrained orgs that cannot send proprietary source code to a hosted API).
- **ALMS sidesteps SOLID's central tension.** SOLID exists because *closed-source*
  models are hard to deploy locally without leaking the model. ALMS uses
  **open-weight** models (`qwen2.5-coder:7b`, `nomic-embed-text`) via Ollama, so
  model confidentiality is a non-issue — ALMS gets the privacy/compliance/offline
  benefits with none of the model-theft problem. This is a clean point to make:
  open local models are the pragmatic path for migration tooling.
- Do **not** cite this for anything about ALMS's architecture, retry loop, or
  decomposition — unrelated.

## Citable sentences
- **Intro / motivation:** privacy-sensitive users "require deploying large language
  models within their own infrastructure (on-premises) to safeguard private data and
  enable customization"; on-prem deployment "preserves control and ensures regulatory
  compliance." Use to justify ALMS running entirely locally rather than calling a
  hosted assistant like the Mono2Sls baselines.
- **Discussion / contrast:** on-prem deployment of *closed* models faces a
  security–customization dilemma; ALMS avoids it by building on open-weight models.

## BibTeX — in paper/refs.bib.
