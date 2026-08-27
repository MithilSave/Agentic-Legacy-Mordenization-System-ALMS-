# Implementation

<!-- STATUS: draft (Claude Code, grounded in the codebase) -->
<!-- TARGET LENGTH: ~1 column / ~650 words -->
<!--
FORMAT NOTES: same as 03-approach.md. Labels used:
  tab:stack   -> a small tech-stack table (compose in Overleaf from the list below)
  fig:statemachine -> paper/figures/statemachine.mmd
All numeric values below are from config.yaml (commit <fill>): model qwen2.5-coder:7b,
embeddings nomic-embed-text; num_ctx analyzer/architect/test_gen 4096, refactoring 6144;
temperature analyzer 0.05, architect 0.1, refactoring 0.2, test_gen 0.15;
rag.relevance_threshold 0.70; chunk_size 500, chunk_overlap 100. Re-confirm before submission.
-->

## Implementation

ALMS is implemented in Python 3.11 in roughly 4k lines across `core/`, `agents/`,
`rag/`, `tools/`, `safety/`, and `storage/`. It has no cloud dependencies and is
designed to run on a single commodity laptop; the reference configuration targets a
16 GB, CPU-only machine.

### Orchestration and models

The pipeline graph is built with LangGraph: a top-level `StateGraph` with the
analysis, boundary, and gate nodes, and a compiled subgraph for the per-service
fan-out that contains the compile--retry cycle (Fig.~\ref{fig:statemachine}).
Parallel branches are dispatched with LangGraph's `Send` API; branch outputs are
merged by a name-keyed reducer on the shared `service_units` channel.

All model inference is local, served by Ollama. Code generation uses
`qwen2.5-coder:7b`; embeddings use `nomic-embed-text` (768-dimensional). Per-agent
context windows are sized to fit the RAM budget rather than maximised: the
Refactoring agent, which needs full function bodies, is given the largest window
(6144 tokens); the Analyzer, Architect, and Test-Gen agents use 4096-token windows.
Sampling temperature is low for analysis (0.05) and boundary reasoning (0.1) and
slightly higher for code (0.2) and test (0.15) generation. Louvain community
detection uses `python-louvain` with a fixed random state.

### Data contracts

Every inter-stage message is a Pydantic v2 model, validated on construction:
`AnalyzerOutput` (statistics, graph nodes/edges, hotspots, external dependencies,
cycles), `ArchitectOutput` (a list of `ServiceBoundary` records with confidence
scores), `RefactoringOutput` (generated files plus a `py_compile` pass flag),
`TestGenOutput` (test cases, shadow-test results, coverage target), and the
per-branch `ServiceUnit` that carries a service through the fan-out with its
compile-attempt count and review status. The orchestrator's own `PipelineState`
records the project id, loaded source, current phase, all agent outputs, the
human-approval history, an iteration counter, and an error list. Because these
contracts are enforced by schema, a malformed agent response is caught at the
boundary rather than propagating downstream, and no model is used to validate another
model's output.

### Retrieval and storage

The knowledge base is a set of Markdown pattern documents (five categories:
refactoring, FastAPI, DDD, security, testing). It is chunked (500 characters, 100
overlap), embedded via Ollama, and stored in a persistent ChromaDB collection using
cosine similarity; retrieval is filtered by a 0.70 minimum-similarity threshold and
scoped per agent. Agent inference outputs are cached in a local
`diskcache` store keyed on the codebase hash, so unchanged inputs do not re-invoke
the model. A SQLite audit database records every agent action (phase, duration,
success, error, structured detail), every human decision (checkpoint, approval,
feedback, iteration), and per-run metadata; it is the source for the timing and
retry statistics reported in the Evaluation. A `rich`-based terminal dashboard
streams pipeline events during a run.

### Artifact and reproducibility

The system is invoked from a single command-line entry point:
`--init-kb` builds the knowledge base, `--demo` runs the pipeline on a bundled
sample monolith, `--skip-hitl` runs unattended, and `--check` verifies the local
environment. Generated output, the vector index, the cache, and the audit database
are all regenerable and excluded from version control. Reproducibility rests on three
choices: a fixed Louvain seed makes boundary selection deterministic; the codebase
hash makes cached runs replay exactly; and local open-weight models remove dependence
on a hosted endpoint whose behaviour can drift between runs. The residual source of
run-to-run variance is the language model's own non-determinism at non-zero
temperature, discussed in the Evaluation.

### Availability

The implementation, the sample monolith, the knowledge base, and the scripts that
regenerate every figure and table in this paper are available at
[repository URL] under [licence].
