# Zan, Chen, Gong, Cao, Zhang, Wu, Guan, Yin, Wang — "Private-Library-Oriented Code Generation with Large Language Models" (APIFinder + APICoder), arXiv:2307.15370, Jul 2023

**bib key:** `zan2023apicoder` — supporting citation for **RAG-grounded code
generation over APIs the model has not seen in pre-training**.

---

## Problem / claim
LLMs (Codex, GPT-4, CODEGEN) generate good code for *public* libraries but fail on
*private* / in-house libraries because they had no exposure to those APIs during
pre-training. Private libraries usually ship API documentation; programmers look up
that doc before writing code. Emulate that.

## Method
Two modules, mirroring the human "API-doc lookup then write":
1. **APIFinder** — dense vector retrieval over the library's API documentation;
   returns candidate APIs for a natural-language requirement; allows optional user
   involvement in the retrieval.
2. **APICoder** — an off-the-shelf code-generation model that is *prompted with the
   retrieved APIs* to write the private code. Also a continued-pre-trained reinforced
   variant, **CODEGENAPI**, trained on many *public* libraries so the skill of
   "invoke APIs given in the prompt" generalises to unseen private ones.
- Index all API docs offline; at query time embed only the problem description and
  retrieve top-N.

## Evaluation setup
- **4 hand-built private-library benchmarks:** TorchDataEval, TorchDataComplexEval,
  MonkeyEval, BeatNumEval, each with hand-written test cases.
- Metric: **pass@k** (k ∈ {1, 10, 100}), also CodeBLEU. 17 code-generation models.
- Settings compared: **No API** (baseline, no retrieval), **Oracle** (gold APIs
  in prompt), **TopN** (APIFinder-retrieved), **Human** (user-assisted retrieval).

## Headline findings
- Providing retrieved API context yields **substantial pass@k gains** over the No-API
  baseline (e.g. up to ~48.6 pp pass@10 improvement on TorchDataEval in an Oracle
  setting); TopN (automatic retrieval) recovers much of the Oracle benefit.
- CODEGENAPI (continued pre-training to follow prompt-supplied APIs) consistently
  beats plain CODEGEN.
- Retrieval quality (Top-5 recall) bounds the achievable gain — the framework is only
  as good as APIFinder.

## How ALMS relates
- **Precedent for ALMS's RAG design.** ALMS's Refactoring / Test-Gen agents run a
  small local model (`qwen2.5-coder:7b`) that has weak/dated knowledge of current
  FastAPI + Pydantic v2 + SQLAlchemy idioms and of DDD/security patterns. ALMS
  retrieves from a local ChromaDB knowledge base of pattern docs
  (`fastapi_patterns`, `security_patterns`, `ddd_patterns`, `testing_patterns`,
  `refactoring_patterns`) and injects them into the prompt — the same
  "retrieve-then-generate against docs the model didn't memorise" pattern APICoder
  formalises for private libraries.
- **Difference:** APICoder retrieves *API signatures* for a *known target library*;
  ALMS retrieves *design/idiom guidance* to steer *how* code is written. Both address
  the same root problem: pre-training coverage gaps, especially acute for **small**
  models.
- Also a precedent for **retriever-only** RAG (no LLM synthesis in the retrieval step)
  — matches ALMS's `AgentRetriever` and Mono2Sls's CodeRAGTool.

## Citable sentences
- **Related work / Approach:** private/unseen APIs pose "a formidable conundrum for
  LLMs, as they inherently lack exposure to these ... during pre-training" — motivates
  RAG for any code generation targeting fast-moving frameworks with a small model.
- **Approach:** their two-module "look up the docs, then write the code" framing is
  the template for ALMS's scoped per-agent retrieval.
- **Evaluation:** retrieval-augmented prompting gives large pass@k gains over no-API
  generation — evidence that RAG is worth the complexity in ALMS.

## BibTeX — in paper/refs.bib (preprint submitted to Elsevier; verify final venue).
