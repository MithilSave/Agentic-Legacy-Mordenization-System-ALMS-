# PROGRESS — Agentic Legacy Modernization System (ALMS)

> Status log for the paper-writing chat: what exists, what works, what was
> recently fixed, what is still open. Pair this with `HANDOFF.md` (architecture).
> Snapshot date: **2026-08-27**. Active branch: **`fix/pipeline-emit-generated`**
> (5 commits ahead of `origin/main`, pushed, **not merged**).

---

## 1. Build status at a glance

| Area | State |
|---|---|
| Static analysis (AST, graph, hotspots, cycles, hash) | **Working**, deterministic, unit-tested |
| Louvain clustering / Architect fallback | **Working**; boundary *quality* is weak (see §5) |
| LangGraph orchestrator (gates, fan-out, retry loop) | **Working**; routing + fan-out unit-tested |
| RAG (KB load, embed, ChromaDB, retrieve) | **Working** with Ollama running; fails loudly if not |
| LLM agents (Analyzer/Architect/Refactoring/Test-Gen) | **Working** with Ollama; not characterised quantitatively |
| Output writer + Docker/compose generation | **Working**; every compose folder now boots |
| Shadow / parity testing | **Partial** — engine exists, not wired to live services |
| LangGraph checkpoint persistence / resumability | **Not implemented** (plan only) |
| Evaluation harness / benchmark | **Not implemented** |

**Test suite (this branch): `25 passed`** — routing, orchestrator fan-out/retry,
constants, audit-logger concurrency, output-writer contract, plus 11
bug-reproduction tests added during the hardening pass below.

---

## 2. Timeline of recent engineering work (this branch)

All commits on `fix/pipeline-emit-generated`, off `origin/main @ 3472ef3`:

| Commit | Summary |
|---|---|
| `bb3e655` | **Fix: dockerisation was broken.** `docker-compose.yml` wired 9 service folders that contained only a `Dockerfile` + `requirements.txt` and no `generated.py`, while the Dockerfile ran `uvicorn generated:app` → every container built then crashed with `ModuleNotFoundError: generated`. Meanwhile the 4 folders that *did* have real code weren't referenced. Added `_ensure_entrypoint()` in `main.py`: reuse the agent's `generated.py` if present, else re-export `app` from another emitted module via a shim, else write a minimal bootable stub (tracked in `pipeline_summary.json → stub_services`). |
| `4d55927` | Tests for the above (`tests/test_save_outputs.py`, 6 cases): empty file list, missing refactoring output, real file preserved, app-in-other-module shim, stub recorded, mixed batch — all fail against pre-fix `main.py`. |
| `59a97b0` | **Three correctness bugs fixed, TDD (red repro test first, then fix):** see §3. Adds `tests/test_dependency_graph_bugs.py`, `tests/test_embedding_failure_bug.py`, `tests/test_architect_fallback_bugs.py` (11 cases). |
| `91b6c2a` | Deleted committed generated output (`examples/migration_output/`) and regenerable runtime state (`chroma_db/`, `cache_db/`, `audit.db`); added `.gitignore`. |
| `6fff5c6` | Untracked all committed `*.pyc` / `__pycache__`. |

Dependencies installed to make the full suite runnable (were missing):
`langgraph`, `langchain-core`, `ollama`, `chromadb`, `radon`, `networkx`,
`python-louvain`, `diskcache`, `black`, `isort`, `hypothesis`.

---

## 3. Bugs found and fixed in the hardening pass

### Bug 1 — dependency graph polluted with non-code symbols (HIGH)
`tools/code_analysis.py::build_dependency_graph` added a node + edge for **every
unresolved call**: Python builtins (`str`, `len`, `round`, `max`), exception
names (`ValueError`), and attribute calls (`logger.info`, `x.hexdigest`,
`datetime.utcnow`). `find_coupling_hotspots` then reported these as "coupled
modules", and — because `networkx.add_edge` auto-creates missing nodes — they
also entered the Louvain graph, producing nonsense service names like
`datetime-hashlib-service`, `sqlite3-cursor-service`, `role_hierarchy-kwargs-service`.
**Fix:** only add edges to resolved internal entities or to known 3rd-party
import roots; filter inheritance edges the same way.
**Effect on the sample monolith:** `134 nodes / 263 edges / 6 noisy hotspots`
→ `75 / 104 / 2 real hotspots`.

### Bug 4 — silent embedding corruption (HIGH for retrieval quality)
`rag/vector_store.py::embed_texts` caught any Ollama error (or empty response)
and appended `[0.0] * 768`. Indexing stored zero-vector documents; queries
ranked a zero query-vector by cosine against the whole collection; no exception
surfaced, so the pipeline reported success on a silently degraded KB.
**Fix:** `embed_texts` raises `RuntimeError`. `query()` catches it and returns
`[]` (logged); `add_documents()` lets it propagate so corrupt vectors are never
persisted.

### Bug 2 — non-deterministic & duplicate service names (MEDIUM/HIGH)
`agents/architect_agent.py::_services_from_communities` built names from
`list(set(modules))[:2]`, so the name depended on set iteration order (varies
across processes), and multiple communities collapsed to the same name
(`models-service` ×N in real output). Downstream, `main.py` keys a compose dict
by name → later services silently overwrite earlier ones.
**Fix:** sort modules, iterate communities in id order, append a numeric suffix
on collision. Fallback on the sample monolith now yields
`app-users-service`, `app-database-service`, `app-database-service-2`, … .

### Still open (found, not fixed — good "future work" / "threats" material)
- `test_analysis.py` / `test_kb.py` (root smoke scripts) crash with
  `UnicodeEncodeError` on cp1252 Windows consoles (`print("✓")` without stdout
  reconfigure).
- `find_coupling_hotspots`: `LOW` severity branch is unreachable when
  `threshold ≥ 3` (default 3).
- `compute_codebase_hash`: concatenates file bytes with no separator →
  theoretical cache-key collision.
- `_analyze_module`: class methods are collected into `structure["functions"]`
  as module-level entries, so `total_functions` double-counts.
- `_resolve_call`: unresolved local call falls back to the first same-named
  function in *any* module.
- Architect decomposition still `app`-hub-heavy; `tables` / `inter_service_calls`
  / `data_ownership` are effectively never populated.

---

## 4. What works end-to-end today

Running `python main.py --demo` with Ollama up:

1. Loads `examples/sample_monolith/` (6 files, 1578 LOC).
2. Analyzer produces a clean dependency graph (75 nodes / 104 edges), 2 coupling
   hotspots, 0 cycles, cyclomatic-complexity avg 2.32, external deps list.
3. Architect runs Louvain (seed 42) → a handful of `ServiceBoundary` proposals
   with confidence scores.
4. (HITL gates auto-approved with `--skip-hitl`.)
5. Fan-out: one subgraph per service → Refactoring agent emits FastAPI code →
   `py_compile` gate → up to 3 regeneration retries → Test-Gen agent emits a
   `pytest` suite (or the service is flagged `needs_human_review`).
6. `_save_outputs` writes `examples/migration_output/` with per-service
   `generated.py` + `Dockerfile` + `requirements.txt`, a `docker-compose.yml`
   where **every** service boots, generated `tests/`, and the three JSON
   artifacts.
7. `audit.db` has the full per-step trace (durations, decisions, retry counts).

---

## 5. Gaps blocking a strong paper (prioritised)

1. **No evaluation.** Need: (a) `py_compile` pass rate and retry-loop firing
   rate across many inputs; (b) behavioural-parity measurement — actually stand
   up the generated services and replay recorded monolith I/O through the
   existing `ShadowTestingEngine`; (c) a baseline to beat (single-shot LLM
   prompt "split this monolith", and/or manual boundaries).
2. **One input.** Need a corpus — e.g. 10–30 small/medium open-source Python
   Flask/Django monoliths, or synthetically generated ones of varying coupling.
3. **No ablations.** The paper's whole thesis is "deterministic structure +
   LLM transformation + validation loop". Ablate each: no-RAG, no-retry-loop,
   no-graph (LLM picks boundaries), no-HITL — and measure the delta.
4. **Model/seed variance not reported.** Run each config N times; report
   mean ± std for every metric. Resolve the `qwen2.5-coder:7b` vs
   `qwen3-coder:30b` config/README mismatch and, ideally, report both.
5. **Boundary-quality metric.** Compare proposed boundaries to a
   human-annotated "gold" decomposition (precision/recall on module→service
   assignment, or modularity / silhouette of the partition).

---

## 6. Suggested next steps (engineering, to enable the paper)

- [ ] Add a `benchmark/` runner: given a directory of monoliths, run the
      pipeline headless, collect metrics to CSV.
- [ ] Wire `ShadowTestingEngine` to `docker compose up` the generated stack and
      replay a captured request log; report exact-match %.
- [ ] Add `--seed` and `--model` CLI flags; log both into `audit.db`.
- [ ] Emit a machine-readable `metrics.json` per run (services, retries,
      needs_review count, compile pass rate, wall-clock per phase, tests
      generated, shadow pass rate).
- [ ] Hand-annotate a gold decomposition for `sample_monolith` + 2–3 others.
- [ ] Fix the open minor bugs in §3 (cheap, removes reviewer nitpicks).
- [ ] (Optional) Add the LangGraph SQLite checkpointer for resumable runs — it
      is a claimed feature.

---

## 7. Reproducibility notes

- Louvain uses `random_state=42`; LLM calls are **not** seeded unless the model
  backend supports it — this is the main source of run-to-run variance.
- DiskCache is keyed on the SHA-256 of the source tree, so re-running on an
  unchanged codebase replays cached agent outputs (delete `cache_db/` to force
  fresh LLM calls).
- All generated artifacts and DBs are git-ignored and regenerable:
  `python main.py --init-kb` rebuilds the KB; a pipeline run rebuilds the rest.
