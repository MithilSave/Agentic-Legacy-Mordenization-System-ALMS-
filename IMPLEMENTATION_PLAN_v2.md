# IMPLEMENTATION_PLAN_v2.md — Architecture Migration Assistant
> Reconciled Plan | CPU-Optimized Local Deployment Edition
> Supersedes conflicting infra details in `ARCHITECTURE_MIGRATION_IMPLEMENTATION_PLAN.md`, `RAG_SYSTEM_DESIGN.md`, `AGENT_PROMPTING_GUIDE.md`, `QUICK_REFERENCE_GUIDE.md`
> Source of truth for architecture decisions: `CONTEXT.md`. This file is the week-by-week execution plan built on top of it.

---

## 0. Why This File Exists

The project has two generations of planning docs living in the same folder:

- **CONTEXT.md** (July 2026, authoritative) — locks in a fully local, CPU-only stack: Ollama, Qwen2.5-Coder:7b, ChromaDB, DiskCache, NetworkX, 16GB RAM laptop, no cloud calls.
- **The older four docs** (`ARCHITECTURE_MIGRATION_IMPLEMENTATION_PLAN.md`, `RAG_SYSTEM_DESIGN.md`, `AGENT_PROMPTING_GUIDE.md`, `QUICK_REFERENCE_GUIDE.md`) — describe an earlier cloud-based version: Pinecone, OpenAI embeddings, Claude 3.5 Sonnet/GPT-4o, Neo4j, Redis, Kubernetes, a 5.5-person team, $326K budget.

**Rule for the team**: infra/deployment decisions always come from CONTEXT.md. The older docs are still useful for *content* — prompt templates, few-shot examples, Pydantic schema shapes, RAG document examples, test patterns — just not for what technology to run them on.

| Where they conflict | Use (CONTEXT.md) | Ignore (older docs) |
|---|---|---|
| LLM | Qwen2.5-Coder:7b local via Ollama | Claude 3.5 Sonnet / GPT-4o |
| Vector DB | ChromaDB (local, `./chroma_db`) | Pinecone / Weaviate |
| Embeddings | nomic-embed-text (local via Ollama) | OpenAI text-embedding-3-small |
| Graph store | NetworkX only | Neo4j |
| Cache | DiskCache | Redis |
| KB size at launch | ~50-80 curated docs (see §2) | 1,050+ / 50K vectors |
| Deployment | Local laptop, no cloud calls | Docker/K8s, Terraform, cloud staging |
| Team size | 3-4 people | 5.5 people, $264K labor |

---

## 1. Team (3-4 people)

| Role | Owns |
|---|---|
| **Person A — Orchestration/RAG lead** | `core/orchestrator.py` (LangGraph state machine), `rag/` module, `config.yaml`, Pydantic schemas in `core/constants.py` |
| **Person B — Analyzer/Architect** | `agents/analyzer_agent.py`, `agents/architect_agent.py`, `tools/code_analysis.py`, Louvain clustering |
| **Person C — Refactoring/Test-Gen** | `agents/refactoring_agent.py`, `agents/test_gen_agent.py`, `tools/code_generation.py`, `tools/testing.py`, py_compile gate |
| **Person D (if 4th)** | `ui/dashboard.py` (Streamlit HITL), `safety/`, `storage/`, audit logging, bandit integration |

If only 3 people: fold D's work into A and C. The HITL dashboard doesn't need to exist until Week 9 — start with a CLI `input()` approval stub instead.

---

## 2. Weeks 1-2 — Foundation (blocks everything else)

Split by owner so this doesn't all serialize through one person. Everyone installs Ollama and pulls the same three models on Day 1 — that part is universal and blocks all four sub-tracks below.

- [ ] **All**: install Ollama, pull `qwen2.5-coder:7b`, `llama3.2:3b`, `nomic-embed-text` — same versions/quantizations on every machine. Confirm `ollama.chat()` returns a response locally before doing anything else. (Budget a full day for this — mismatched quantizations, slow first pulls, and RAM surprises on lower-spec laptops are the most common early derailment on a CPU-only local stack.)

**Person A — orchestrator + config:**
- [ ] `config.yaml` per CONTEXT.md §5 — per-agent `num_ctx`, not a flat 8192 for everyone
- [ ] LangGraph orchestrator skeleton with the `State` dict from the implementation plan doc, wired to mock agents that just echo input, to prove the graph runs end to end
- [ ] Pydantic schemas for **Analyzer and Architect outputs only** in `core/constants.py` (the two agents starting Week 3). Defer Refactoring/Test-Gen schemas to Weeks 5-6 and 7-8 respectively, owned by Person C at that point — writing them now, before those agents are designed, just invites rework

**Person B — sample data:**
- [ ] Build `examples/sample_monolith/` — a small Flask app, ~300-500 LOC, 3 modules (users/orders/payments style, matching the example in `AGENT_PROMPTING_GUIDE.md` §1.2). This is the fixture you demo against for all 12 weeks — get it right now. No dependency on A's work, so this runs in parallel

**Person C (or D) — RAG + KB:**
- [ ] ChromaDB local persistent client (`./chroma_db`) — not Pinecone/Weaviate
- [ ] Own KB curation end to end: **~50-80 hand-picked docs**, `fastapi_patterns` + `refactoring_patterns` only. Add `ddd_patterns` in Week 3 when Architect needs it, `testing_patterns` in Week 7. Do not start with 200 or 1,050 — validate retrieval quality on a small set first, per CONTEXT.md's own recommendation in §18

**Exit check (hard gate — don't start Week 3 until all pass)**:
- `ollama.chat()` succeeds locally on every machine
- ChromaDB returns results for a test query against the curated KB
- Orchestrator runs a no-op graph end to end
- `sample_monolith/` exists and is committed

Build in a **2-day buffer** at the end of Week 2 for whichever of these slips — on a team new to local LLM orchestration, something usually does.

---

## 3. Weeks 3-4 — Analyzer + Architect Agents

### Analyzer (Person B)
- [ ] `tools/code_analysis.py`: implement `extract_code_structure()` exactly as in CONTEXT.md §9 — AST-only, function/class/import/global-var extraction
- [ ] Confirm the AST pre-filter is wired **only** here — this is the #1 listed pitfall in CONTEXT.md §15
- [ ] `agents/analyzer_agent.py`: Ollama call with `format="json"`, `num_ctx=4096`, `temperature=0.05`
- [ ] RAG retrieval scoped to `refactoring_patterns` only, `top_k=3`
- [ ] Validate output against the dependency-graph Pydantic model before handoff
- [ ] `radon` for complexity metrics, `NetworkX` for the graph object
- [ ] Cache via `diskcache`, keyed on codebase SHA-256 hash (CONTEXT.md §11 pattern)

### Architect (Person B)
- [ ] Louvain clustering on the Analyzer's NetworkX graph
- [ ] RAG retrieval scoped to `ddd_patterns`, `top_k=3`
- [ ] `agents/architect_agent.py` using the `ServiceBoundary` / `ArchitectOutput` Pydantic models from CONTEXT.md §9

### HITL stub (Person A, not B)
- [ ] **First HITL checkpoint** (CONTEXT.md §13) — a CLI `input()` approval gate that plugs into the orchestrator Person A already owns, rather than deferring human review to Week 9 or loading it onto Person B, who's already carrying both agents this sprint

**Exit check**: run Analyzer → Architect on `sample_monolith/`, get a schema-valid `microservice_boundaries.json` with confidence scores, reviewed by a human (CLI is fine).

**Watch out for**: both agents share one model (`qwen2.5-coder:7b`) per CONTEXT.md's single-model decision. Don't let a dev environment silently pull a different model/quant because an older doc mentions Mistral or GPT-4o.

---

**Integration checkpoint (end of Week 4)**: full team runs Analyzer → Architect → HITL approval on `sample_monolith/` together, live, not just individually. Catching orchestrator/schema mismatches here is cheap; catching them in Week 11 is not.

## 4. Weeks 5-6 — Refactoring Agent (Person C)

- Person C now writes the Refactoring output Pydantic schema (deferred from Week 1-2, see §2) before starting the agent itself
- `num_ctx: 6144` — only agent needing this; watch total RAM stays under ~11-12GB with it loaded
- AST pre-filter **must not** apply here — needs full function bodies
- Jinja2 templates + LibCST for transforms, `black`/`isort` post-gen, `py_compile` gate before Test-Gen handoff
- RAG scoped to `fastapi_patterns`, plus one `security_patterns` doc (pattern from `RAG_SYSTEM_DESIGN.md`'s Refactoring Agent Retriever section)

**Integration checkpoint (end of Week 6)**: run the full Analyzer → Architect → Refactoring chain on `sample_monolith/`. Confirm the `py_compile` gate actually catches a deliberately broken generation before trusting it on real output.

## 5. Weeks 7-8 — Test-Gen + Shadow Testing (Person C)

- Test-Gen output schema written at the start of this phase, not before
- pytest + hypothesis property tests
- Shadow testing engine: legacy vs. generated, exact-match comparison, sampled subset (~15-20 representative cases, not every endpoint — full coverage doubles demo time)
- **Second HITL checkpoint** here (CONTEXT.md §13)

**Integration checkpoint (end of Week 8)**: full pipeline, Analyzer through shadow testing, on `sample_monolith/`, timed. This is your first real read on whether the CONTEXT.md §14 estimate (~45-75 min single-service E2E) is holding — if it's running much longer, that's a Week 9-10 problem to solve, not a Week 12 surprise.

## 6. Weeks 9-10 — HITL Dashboard + Safety (Person D / whoever's free)

- Streamlit dashboard with `st.write_stream()` for live code generation
- `bandit` scan — block only on HIGH severity + HIGH confidence; medium/low surface as warnings
- SQLite audit log
- **Skip** the Docker sandbox unless there's slack time — CONTEXT.md marks it optional for the capstone demo, and it's the most cloud/infra-heavy leftover from the old plan

## 7. Weeks 11-12 — Integration + Capstone Prep

- Pre-cache Analyzer + Architect outputs so the live demo starts from Refactoring — cuts demo time to ~25-35 min (CONTEXT.md §14)
- Scope the live demo to **1 service**, not 5 — a 5-service E2E run is 5-7 hours per CONTEXT.md's own performance table
- Prepare before/after code comparison, shadow test parity report, audit trail, and ROI slide

---

## 8. Decisions Locked In Now (from CONTEXT.md §18 "Open Decisions")

| Decision | Choice | Why |
|---|---|---|
| KB scope at launch | 50-80 curated docs | Validate retrieval quality before expanding; matches CONTEXT.md's own "start with 200, not 1,050" logic, scaled down further for a faster Week 1-2 |
| Docker sandbox | Skip for demo | Optional per CONTEXT.md; `bandit` static scanning is the safety net instead |
| HITL escalation policy | Escalate immediately after 3 retries | Avoids adding temperature-increase nondeterminism right before a live demo |
| Shadow testing scope | Statistically sampled subset (~15-20 cases) | Full endpoint testing doubles demo time for marginal parity-confidence gain |

---

## 9. Known Pitfalls (carried over from CONTEXT.md §15 — do not relearn these the hard way)

| Pitfall | What goes wrong | Fix |
|---|---|---|
| `num_ctx: 8192` for all agents | Pushes peak RAM into swap on 16GB machines (0.5 tok/s) | Per-agent context windows per §2 config |
| LLM validating LLM output | Both models share failure modes; wrong output gets confirmed | Pydantic schema validation — zero tokens, deterministic |
| AST pre-filter applied everywhere | Strips function bodies from Refactoring/Test-Gen context | Apply only to Analyzer |
| Token-count chunking | Splits functions mid-definition | File/class-level chunking |
| 5-service live demo | 5-7 hours, will fail on stage | Pre-cache first two agents; demo 1 service from Refactoring onward |
| Switching models between agents | 30-60s swap penalty per transition on CPU | Single model (Qwen2.5-Coder:7b) for all 4 main agents |
| Injecting low-relevance RAG context | Degrades output quality with noise | Relevance threshold filter, cosine sim ≥ 0.70 |

---

## 10. Next Concrete Steps

1. Team assigns roles per §1 this week — confirm who's the 3rd/4th person now that Week 1-2 work is split three ways (orchestrator, sample data, RAG/KB) rather than stacked on one person.
2. Everyone installs Ollama and pulls the three models on Day 1 — don't let this slip to Day 3, it's the one true blocker for all three sub-tracks.
3. Person A, B, and C-or-D start their Week 1-2 tracks in parallel per §2.
4. Reconvene at the end of Week 2 for the hard-gate exit check in §2, with the 2-day buffer already accounted for, before starting Analyzer/Architect work.
5. Put the four integration checkpoints (end of Weeks 4, 6, 8, 10) on the calendar now, not as an afterthought — they're what keeps Week 11-12 from being a big-bang integration scramble.
