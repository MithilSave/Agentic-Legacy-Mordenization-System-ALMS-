# Architecture Migration Assistant — Build Plan

Build the complete multi-agent Architecture Migration Assistant as described in `IMPLEMENTATION_PLAN_v2.md`, using the locally installed `qwen2.5:7b` model via Ollama, ChromaDB for RAG, and a retro DOS-style terminal UI for the capstone demo.

## Scope

Build the **full Week 1-2 foundation** plus the **Analyzer & Architect agents** with a working sample monolith to demo against — this is what's needed to have a runnable, impressive capstone deliverable.

## Proposed Changes

### 1. Project Structure

Create the full directory scaffold as specified in the architecture plan:

```
Capston/
├── core/
│   ├── __init__.py
│   ├── orchestrator.py          # LangGraph-style state machine
│   ├── config.py                # YAML config loader
│   └── constants.py             # Pydantic schemas, prompt templates
├── agents/
│   ├── __init__.py
│   ├── analyzer_agent.py        # AST analysis + dependency graph
│   ├── architect_agent.py       # DDD bounded context proposals
│   ├── refactoring_agent.py     # FastAPI code generation
│   └── test_gen_agent.py        # Test suite generation
├── rag/
│   ├── __init__.py
│   ├── vector_store.py          # ChromaDB integration
│   ├── knowledge_base.py        # Document loader & indexer
│   └── retriever.py             # Agent-specific retrieval
├── tools/
│   ├── __init__.py
│   ├── code_analysis.py         # AST parsing, metrics (radon)
│   ├── code_generation.py       # Jinja2 templates, LibCST
│   └── testing.py               # Shadow testing engine
├── safety/
│   ├── __init__.py
│   └── validator.py             # py_compile gate, bandit scan
├── storage/
│   ├── __init__.py
│   ├── cache.py                 # DiskCache wrapper
│   └── audit_logger.py          # SQLite audit log
├── ui/
│   ├── __init__.py
│   └── dashboard.py             # DOS-style terminal UI (Rich)
├── examples/
│   └── sample_monolith/         # Flask app ~300-500 LOC
│       ├── app.py
│       ├── models.py
│       ├── users.py
│       ├── orders.py
│       ├── payments.py
│       └── database.py
├── knowledge_base/              # Curated KB docs (~50-80)
│   ├── refactoring_patterns/
│   ├── fastapi_patterns/
│   ├── ddd_patterns/
│   └── security_patterns/
├── config.yaml                  # Per-agent model config
├── requirements.txt
└── main.py                      # CLI entry point
```

---

### 2. Sample Monolith (`examples/sample_monolith/`)

#### [NEW] `app.py`, `models.py`, `users.py`, `orders.py`, `payments.py`, `database.py`

A Flask-style monolith (~400 LOC) with 3 tightly coupled modules:
- **Users**: authentication, profile management, password hashing
- **Orders**: order creation, status tracking, depends on Users + Payments
- **Payments**: payment processing, refunds, depends on Users (circular dep)

This matches the example in `AGENT_PROMPTING_GUIDE.md` §1.2. Will include deliberate coupling issues, circular imports, global state, and complexity hotspots for the Analyzer to find.

---

### 3. Core System

#### [NEW] `config.yaml`
Per-agent `num_ctx` settings as specified in CONTEXT.md §5:
- Analyzer: `num_ctx: 4096`, `temperature: 0.05`
- Architect: `num_ctx: 4096`, `temperature: 0.1`
- Refactoring: `num_ctx: 6144`, `temperature: 0.2`
- Test-Gen: `num_ctx: 4096`, `temperature: 0.15`

#### [NEW] `core/config.py`
YAML config loader with model endpoint settings pointing to local Ollama.

#### [NEW] `core/constants.py`
Pydantic schemas for:
- `AnalyzerOutput` (dependency graph nodes/edges, hotspots, metrics)
- `ArchitectOutput` (proposed services, bounded contexts, confidence scores)
- `RefactoringOutput` (generated code, service definition)
- `TestGenOutput` (test suite, coverage metrics)

Plus system prompt templates from `AGENT_PROMPTING_GUIDE.md`.

#### [NEW] `core/orchestrator.py`
State machine implementing the pipeline:
`Analyze → Architect → [HITL] → Refactor → TestGen → [HITL] → Done`

Uses a simple state dict (no LangGraph dependency — keeps it lightweight for local CPU):
```python
State = {
    "project_id": str,
    "source_code": str,
    "dependency_graph": dict,
    "microservice_boundaries": list,
    "generated_services": dict,
    "test_suite": dict,
    "human_approvals": list,
    "iteration_count": int,
    "current_phase": str
}
```

---

### 4. Agents

#### [NEW] `agents/analyzer_agent.py`
- AST parsing via `tools/code_analysis.py`
- Ollama call with `format="json"`, `num_ctx=4096`, `temperature=0.05`
- RAG retrieval scoped to `refactoring_patterns`, `top_k=3`
- Pydantic validation of output
- DiskCache keyed on codebase SHA-256

#### [NEW] `agents/architect_agent.py`
- Louvain clustering on NetworkX graph from Analyzer
- RAG retrieval scoped to `ddd_patterns`, `top_k=3`
- Outputs `ServiceBoundary` Pydantic models with confidence scores

#### [NEW] `agents/refactoring_agent.py`
- `num_ctx: 6144` — needs full function bodies (no AST pre-filter)
- Jinja2 templates for FastAPI service structure
- `py_compile` gate before output
- RAG scoped to `fastapi_patterns` + `security_patterns`

#### [NEW] `agents/test_gen_agent.py`
- pytest + hypothesis property tests generation
- Shadow testing comparison logic
- RAG scoped to `testing_patterns`

---

### 5. RAG System

#### [NEW] `rag/vector_store.py`
ChromaDB local persistent client at `./chroma_db`:
- `nomic-embed-text` embeddings via Ollama
- Cosine similarity with threshold ≥ 0.70
- Metadata filtering by category

#### [NEW] `rag/knowledge_base.py`
- Markdown document loader
- Semantic chunking (file/class-level, NOT token-count)
- Batch indexing into ChromaDB

#### [NEW] `rag/retriever.py`
Agent-specific retrievers with scoped category filters.

#### [NEW] `knowledge_base/` docs
~20 curated docs across 4 categories to start (enough for demo):
- `refactoring_patterns/`: 5 Flask→FastAPI transformation examples
- `fastapi_patterns/`: 5 routing/DI/error-handling patterns
- `ddd_patterns/`: 5 bounded context/aggregate root examples
- `security_patterns/`: 5 input validation/auth patterns

---

### 6. Tools

#### [NEW] `tools/code_analysis.py`
`extract_code_structure()` — AST-only extraction per CONTEXT.md §9:
- Functions, classes, imports, global variables
- Radon cyclomatic complexity metrics
- NetworkX dependency graph construction

#### [NEW] `tools/code_generation.py`
Jinja2 templates for FastAPI service scaffolding + `black`/`isort` formatting.

#### [NEW] `tools/testing.py`
Shadow testing engine for legacy vs. generated output comparison.

---

### 7. DOS-Style Terminal UI (`ui/dashboard.py`)

A retro DOS-style terminal interface using the **Rich** library:

- Green-on-black text with ASCII art banner
- Blinking cursor effect and typewriter-style text output
- Box-drawn panels for agent status, progress bars
- ASCII flowchart showing pipeline progress
- Real-time streaming of agent output
- CLI `input()` HITL approval gates at checkpoints
- Color-coded severity indicators (█ blocks)

This gives the capstone demo a distinctive, memorable look.

---

### 8. Storage & Safety

#### [NEW] `storage/cache.py` — DiskCache wrapper keyed on SHA-256
#### [NEW] `storage/audit_logger.py` — SQLite audit trail
#### [NEW] `safety/validator.py` — `py_compile` gate + basic security checks

---

### 9. Entry Point

#### [NEW] `main.py`
CLI that:
1. Loads config
2. Initializes RAG/ChromaDB
3. Launches the DOS-style UI
4. Runs the orchestrator pipeline on the sample monolith (or user-provided path)
5. Supports `--init-kb` flag to populate the knowledge base

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| LLM | `qwen2.5:7b` via Ollama (already downloaded) | Per IMPLEMENTATION_PLAN_v2 — single model, no swap penalty |
| Embeddings | `nomic-embed-text` via Ollama | Local, no cloud calls |
| Vector DB | ChromaDB (local `./chroma_db`) | Per CONTEXT.md — no Pinecone |
| Graph store | NetworkX only | Per CONTEXT.md — no Neo4j |
| Cache | DiskCache | Per CONTEXT.md — no Redis |
| UI | Rich terminal (DOS-style) | Distinctive capstone look, no Streamlit dependency |
| Orchestrator | Simple state machine | No LangGraph dependency — lighter for CPU |

## Verification Plan

### Automated Tests
```bash
python main.py --init-kb          # Populate knowledge base 
python main.py examples/sample_monolith  # Run full pipeline
```

### Manual Verification
- Confirm Ollama responds to `ollama.chat()` calls
- ChromaDB returns results for test queries
- Analyzer produces valid dependency graph JSON
- Architect produces bounded context proposals with confidence scores
- DOS UI renders correctly with all visual effects
- HITL approval gates pause and wait for input
