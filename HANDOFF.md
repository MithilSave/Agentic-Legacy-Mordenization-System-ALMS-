# HANDOFF — Agentic Legacy Modernization System (ALMS)

> Self-contained technical description of the project, written to be pasted into a
> fresh Claude chat as context for drafting a research paper. Everything here
> reflects the **actual code on branch `fix/pipeline-emit-generated`** as of
> 2026-08-27, not aspirational design. Where the code and the original plan
> diverge, this document follows the code and flags the gap.

---

## 1. One-paragraph summary

ALMS is a locally-hosted, multi-agent pipeline that takes a legacy Python
monolith as input and emits a set of containerised FastAPI microservices with
generated test suites. It combines **deterministic static analysis** (Python
`ast` + `networkx` call-graph + Louvain community detection) with **LLM code
generation** (local models via Ollama), **retrieval-augmented prompting**
(ChromaDB over a small hand-authored knowledge base of migration/DDD/FastAPI
patterns), and **human-in-the-loop (HITL) gates**. Orchestration is a LangGraph
`StateGraph` with a per-service parallel fan-out (`Send` API) and an isolated
compile-retry loop. The design thesis: *keep structure extraction and validation
deterministic and outside the LLM; use the LLM only for the transformation step
it is actually good at, inside a validation loop.*

---

## 2. Problem statement

Migrating a monolith to microservices is normally weeks–months of manual work:
identifying seams, defining service boundaries, rewriting endpoints, re-testing
for behavioural parity. Existing LLM approaches tend to do this in one shot with
no structural grounding, producing plausible-looking but unvalidated code and
arbitrary boundaries. ALMS targets three failure modes specifically:

1. **Boundary selection** — done from a real dependency graph + community
   detection, not from LLM vibes.
2. **Structural hallucination** — every generated service passes `py_compile`
   before it is accepted; failures loop back to regeneration.
3. **Silent quality loss** — deterministic Pydantic schemas validate every
   agent's output (no "LLM checking LLM"), and RAG failures raise instead of
   degrading silently.

---

## 3. Architecture

### 3.1 Pipeline (LangGraph `StateGraph`)

```
START
  → analyze                (Analyzer agent: AST + graph + hotspots)
  → hitl_analyze           (HITL gate 1: "after_analyze")
        approve → architect / reject → analyze / stop → END
  → architect              (Architect agent: Louvain → ServiceBoundary[])
  → hitl_architect         (HITL gate 2: "after_architect")
        approve → fan-out  / reject → architect / stop → END
  → process_service  ×N    (parallel Send, one per proposed service)
        │  subgraph per service:
        │    refactor_service → validate_service
        │       ├─ pass         → test_gen_service → END
        │       ├─ retry (<3)   → refactor_service   (compile-retry loop)
        │       └─ needs_review → mark_needs_review → END
  → join                   (merge branch results by service name)
  → hitl_final             (HITL gate 3: "after_test_gen")
        approve → END / reject → re-run fan-out / stop → END
```

- **State channels** (`core/orchestrator.py`): `state: PipelineState` (replace
  semantics) and `service_units: Annotated[List[ServiceUnit], _replace_by_service_name]`.
  The custom reducer merges parallel branches by `service.name` so re-runs
  replace rather than duplicate — this fixes the classic `operator.add`
  fan-out duplication bug.
- **Retry loop** is a genuine graph cycle inside the subgraph, bounded by
  `config.max_retries` (default 3). `next_compile_action()` returns
  `pass | retry | needs_review`.
- **HITL routing** via `route_after_hitl(approved, feedback)` →
  `approve | reject | fail`; `fail` triggers on feedback keywords
  `quit|exit|stop|fail`. `--skip-hitl` auto-approves every gate.

### 3.2 Agents (`agents/`)

| Agent | Input | Output schema | LLM ctx | RAG scope |
|---|---|---|---|---|
| **Analyzer** | source dir | `AnalyzerOutput` (stats, nodes, edges, hotspots, external deps, cycles) | 4096 | `refactoring_patterns` |
| **Architect** | `AnalyzerOutput` | `ArchitectOutput` (`ServiceBoundary[]` with confidence + reason) | 4096 | `ddd_patterns` |
| **Refactoring** | one `ServiceBoundary` + full source | `RefactoringOutput` (`GeneratedFile[]`, `py_compile_passed`) | 6144 | `fastapi_patterns`, `security_patterns` |
| **Test-Gen** | `RefactoringOutput` + source | `TestGenOutput` (`TestCase[]`, shadow results, coverage target) | 4096 | `testing_patterns` |

Key discipline (from `CONTEXT.md` notes in the code): the **AST pre-filter is
applied only to the Analyzer**. Refactoring and Test-Gen receive full function
bodies — stripping them there was an explicitly-called-out pitfall.

### 3.3 Deterministic analysis (`tools/code_analysis.py`)

- `extract_code_structure()` — AST walk → functions (name, params, calls,
  cyclomatic complexity, LOC, docstring), classes (methods, bases), imports,
  module-level globals.
- `build_dependency_graph()` — `networkx.DiGraph`: nodes = modules / functions /
  classes; edges = resolved internal calls, genuine 3rd-party calls, imports,
  inheritance. **Unresolved calls (builtins, stdlib methods, local-variable
  methods) are dropped** so they don't pollute coupling or clustering.
- `find_coupling_hotspots()` — modules with ≥ `threshold` cross-module edges,
  severity HIGH/MEDIUM.
- `find_circular_dependencies()` — `nx.simple_cycles`.
- `compute_codebase_hash()` — SHA-256 over sorted file bytes; used as the
  DiskCache key so re-runs on an unchanged codebase are cache hits.

### 3.4 Clustering (`agents/architect_agent.py`)

- Rebuilds an **undirected** weighted graph from `AnalyzerOutput.edges`
  (weight = edge confidence).
- `python-louvain` `best_partition(random_state=42)` → `node_id → community_id`.
- If the LLM returns structured services, those are used; otherwise
  `_services_from_communities()` derives one `ServiceBoundary` per community:
  name = first two (sorted) module names + `-service`, deduplicated with a
  numeric suffix on collision.

### 3.5 RAG (`rag/`)

- `knowledge_base.py` — loads `knowledge_base/<category>/*.md` (9 docs, ~330
  lines total, 5 categories), chunks (size 500 / overlap 100), embeds, upserts.
- `vector_store.py` — ChromaDB `PersistentClient` (`./chroma_db`), cosine space;
  embeddings via Ollama `nomic-embed-text` (768-dim). `embed_texts()` **raises
  `RuntimeError` on backend error or empty response** (never substitutes a zero
  vector). `query()` catches that and returns `[]`; `add_documents()` lets it
  propagate so corrupt vectors are never indexed. Relevance threshold 0.70.
- `retriever.py` — `AgentRetriever` maps each agent to its allowed KB categories
  and `top_k` (all 3), merges per-category results, formats for prompt injection.

### 3.6 Validation & output

- `tools/code_generation.py` — Jinja2 service/test templates (currently the
  pipeline relies on raw LLM code + `validate_syntax()` more than the
  templates), `format_code()` (isort + black, best-effort), `validate_syntax()`
  (`py_compile` in a temp file).
- `safety/validator.py` — `CodeValidator`: `py_compile`, AST-parseable, required
  patterns (imports / type hints), optional Bandit scan.
- `tools/testing.py` — `ShadowTestingEngine`: runs identical inputs through a
  legacy callable and a new callable, exact-match compare, records
  discrepancies (difflib). Intended for a sampled ~15–20 cases.
- `main.py::_save_outputs()` writes `examples/migration_output/`:
  - `<Service>/generated.py`, `<Service>/Dockerfile`, `<Service>/requirements.txt`
  - `docker-compose.yml` (one service per folder, ports 8000..800N)
  - `tests/*.py`
  - `analyzer_output.json`, `architect_output.json`, `pipeline_summary.json`
  - `_ensure_entrypoint()` guarantees every compose folder has a `generated.py`
    exposing `app`: use the agent's file if present, else re-export `app` from
    another emitted module via a shim, else write a minimal bootable stub
    (recorded under `pipeline_summary.json → stub_services`).

### 3.7 Storage / observability

- `storage/audit_logger.py` — SQLite (`audit.db`): pipeline runs, per-agent
  actions (phase, duration_ms, success, details), HITL decisions.
- `storage/cache.py` — `diskcache` (`./cache_db`, 1 GB cap) for agent outputs
  keyed on codebase hash.
- `ui/dashboard.py` — `rich` terminal dashboard (retro DOS aesthetic): banner,
  phase table, live event stream, HITL prompts.

---

## 4. Technology stack

| Concern | Choice |
|---|---|
| Orchestration | LangGraph (`StateGraph`, `Send` fan-out, subgraph cycles) |
| LLM runtime | Ollama, local. `config.yaml` sets `qwen2.5-coder:7b`; README example uses `qwen3-coder:30b` (**discrepancy — pick one for the paper**) |
| Embeddings | Ollama `nomic-embed-text` (768-dim) |
| Vector DB | ChromaDB (local, SQLite-backed), cosine |
| Static analysis | `ast`, `radon`, `networkx`, `python-louvain` |
| Schemas | Pydantic v2 (agent I/O contracts) |
| Codegen post-proc | Jinja2, `black`, `isort`, `py_compile` |
| Security | Bandit (optional hook) |
| Tests (generated) | `pytest`, `hypothesis` |
| Target services | FastAPI + SQLAlchemy + Pydantic, Docker / docker-compose |
| Cache / audit | `diskcache`, SQLite |
| UI | `rich` |
| Sample input | `flask` monolith in `examples/sample_monolith/` |

Design constraint throughout: **fully local, CPU-friendly, no cloud calls**
(targets a 16 GB laptop; per-agent context windows are sized to fit RAM).

---

## 5. Data contracts (Pydantic, `core/constants.py`)

- `AgentPhase`: init → analyzing → architecting → refactoring → testing →
  complete / failed
- `AnalyzerOutput`: `codebase_stats`, `nodes[]`, `edges[]` (`EdgeType`:
  internal_call / external_call / import / inheritance / db_access),
  `hotspots[]` (`Severity`), `external_dependencies[]`, `circular_dependencies[]`
- `ServiceBoundary`: `name`, `bounded_context`, `modules[]`, `tables[]`,
  `endpoints[]`, `inter_service_calls[]`, `external_dependencies[]`,
  `confidence_score` (0–1), `reason`
- `ArchitectOutput`: `proposed_services[]`, `inter_service_patterns`,
  `data_ownership`
- `RefactoringOutput`: `service_name`, `files[]` (`GeneratedFile{filename,
  content}`), `py_compile_passed`, notes
- `TestGenOutput`: `test_cases[]`, `shadow_results`, `total_tests`, coverage
  target
- `ServiceUnit` (per fan-out branch): `service`, `refactoring_output`,
  `test_gen_output`, `compile_attempts`, `needs_human_review`, `status`
- `PipelineState`: `project_id`, `source_path`, `source_code{}`, `current_phase`,
  `analyzer_output`, `architect_output`, `service_units[]`, `human_approvals[]`,
  `iteration_count`, `errors[]`

---

## 6. How to run

```bash
# prerequisites: Ollama running, models pulled
ollama pull qwen2.5-coder:7b        # or qwen3-coder:30b
ollama pull nomic-embed-text
pip install -r requirements.txt

python main.py --init-kb           # build the ChromaDB knowledge base
python main.py --demo              # run on examples/sample_monolith/
python main.py --skip-hitl <path>  # run on an arbitrary Python project, no gates
python main.py --check             # environment / Ollama connectivity check
```

Output lands in `examples/migration_output/` (git-ignored).

---

## 7. Sample input characteristics (`examples/sample_monolith/`)

Flask monolith, deterministic analysis result:

- 6 files, 1578 lines, 76 functions, 7 classes, avg cyclomatic complexity 2.32
- Modules: `app`, `database`, `models`, `orders`, `payments`, `users`
- After the dependency-graph fix: 75 graph nodes, 104 edges, 2 coupling
  hotspots — `app → {database, orders, payments, users}` and
  `orders → {database, models, payments, users}` (i.e. `app` and `orders` are
  the real god-modules). 0 circular dependencies.

---

## 8. Known limitations / honest gaps (important for "threats to validity")

1. **Evaluation is thin.** Success metrics in the plan are `py_compile` pass
   rate and "pipeline reaches END". There is no behavioural-parity number, no
   comparison against a baseline (one-shot LLM, or manual), no multi-project
   benchmark. The shadow-testing engine exists but is not wired to actually
   stand up the generated services and replay real traffic.
2. **Single sample input.** Everything is demonstrated on one ~1.5 kLOC Flask
   monolith. No generalisation evidence.
3. **Boundary quality.** Louvain on a call graph with an `app` hub tends to
   pull `app` into most communities, so proposed services overlap on `app`.
   `tables: []` and `inter_service_calls: []` are essentially always empty —
   data ownership is not actually derived.
4. **LLM dependence not characterised.** No numbers on how often the
   compile-retry loop fires, how many services hit `needs_review`, or
   variance across models / seeds / runs.
5. **Generated services are skeletal.** They compile and boot, but business
   logic fidelity vs the monolith is unquantified.
6. **Model config mismatch** between README and `config.yaml`.
7. **Minor code issues** still open (found, not fixed): Unicode crash in the
   root `test_analysis.py` / `test_kb.py` scripts on Windows consoles; a dead
   `LOW` severity branch; `compute_codebase_hash` concatenates file bytes with
   no delimiter (theoretical collision); class methods are counted as
   module-level functions in stats; `_resolve_call` falls back to first
   same-named function in any module.
8. **LangGraph checkpointing** (SQLite persistence / resumability) is described
   in the plan but the orchestrator calls `graph.invoke(...)` with no
   checkpointer — runs are not resumable.

---

## 9. Repository map

```
core/         config.py · constants.py (schemas+prompts) · orchestrator.py (LangGraph)
agents/       analyzer_agent · architect_agent · refactoring_agent · test_gen_agent
rag/          knowledge_base · vector_store · retriever
tools/        code_analysis (AST+graph) · code_generation (jinja/black/py_compile) · testing (shadow)
safety/       validator.py (py_compile + bandit)
storage/      audit_logger.py (SQLite) · cache.py (diskcache)
ui/           dashboard.py (rich)
knowledge_base/  9 markdown pattern docs in 5 categories
examples/     sample_monolith/ (input) · migration_output/ (generated, git-ignored)
tests/        core/ (routing, orchestrator fan-out, constants) · storage/ · pipeline + bug-repro suites
main.py       CLI entry point + output writer + docker-compose generator
config.yaml   models, per-agent ctx/temp/RAG, thresholds, HITL checkpoints
```
