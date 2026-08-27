# Approach

<!-- STATUS: draft (Claude Code, grounded in the codebase) -->
<!-- TARGET LENGTH: ~2.5 columns / ~1500 words -->
<!--
FORMAT NOTES for Cowork / Overleaf:
- Markdown headers map to LaTeX: `##` -> \section, `###` -> \subsection.
- Inline \cite{...} and \ref{...}/\autoref{...} are already LaTeX; keep them.
- Figure/table labels used here (define these in Overleaf):
    fig:pipeline      -> paper/figures/pipeline.mmd  (end-to-end pipeline)
    fig:statemachine  -> paper/figures/statemachine.mmd  (LangGraph StateGraph)
    fig:graph         -> paper/figures/graph_before_after.pdf
    tab:related       -> paper/tables/related-work-comparison.md
- Every quantitative claim below is a system property, not a result; results live
  in the Evaluation section.
-->

## Approach

### Overview

ALMS takes a directory of Python source files as input and produces a set of
containerised FastAPI services, one generated test suite per service, and a
`docker-compose.yml` that runs them together. The transformation is organised as a
seven-stage pipeline (Fig.~\ref{fig:pipeline}): **(1)** deterministic structural
analysis, **(2)** service-boundary identification, **(3)** a human review gate,
**(4)** per-service code generation inside a compile–retry loop, **(5)** per-service
test generation, **(6)** a second human review gate, and **(7)** artifact
serialisation. Stages 1–2 use no language model; stages 4–5 use a single local
model; a retrieval component supplies pattern guidance to every LLM stage.

The design is organised around one principle: **keep everything that can be made
deterministic outside the language model, and give the model only the transformation
step it is actually good at.** Boundary selection is a graph-clustering problem, so
ALMS solves it with community detection rather than prompting. Output validation is a
compiler problem, so ALMS gates every generated service with `py_compile` and loops
on failure. Inter-stage data contracts are schema-validation problems, so ALMS
encodes them as typed records that are checked without a model in the loop --- an
LLM is never asked to judge another LLM's output \cite{chen2026mono2sls}. What
remains for the model is: given a bounded set of source modules, a target framework,
and retrieved idioms, emit the corresponding service. This division is what lets a
7B model running on a laptop stand in for the hosted commercial assistants used by
comparable pipelines; prior work reports that pipeline structure contributes more to
migration quality than backbone-model strength \cite{chen2026mono2sls,
sellami2025monoembed}.

### Deterministic Structural Analysis

The Analyzer parses every `.py` file with Python's `ast` module and extracts, per
module: function definitions (name, parameters, called names, cyclomatic complexity,
lines of code, docstring), class definitions (methods, base classes), `import` and
`from ... import` statements, and module-level assignments. Cyclomatic complexity is
computed by counting decision points (`if`, `for`, `while`, `except`, boolean
operators, comprehensions) rather than invoking an external tool, so the metric is
reproducible across environments.

From this structure the Analyzer builds a directed dependency graph whose nodes are
modules, functions, and classes. Edges are added only for relationships that
correspond to real code entities: a call is linked to its resolved internal target
if one exists, or to a third-party module if the call's head matches a known import;
inheritance edges are added only to classes or imported modules that the analysis
actually observed. Calls that resolve to Python builtins, standard-library methods,
or local-variable methods are **not** added as edges, because they are not
architectural dependencies and would otherwise dominate both the coupling analysis
and the subsequent clustering (Fig.~\ref{fig:graph}). The graph is then reduced to a
list of coupling hotspots (modules with cross-module fan-out above a threshold) and a
set of circular dependencies (via strongly connected components). A SHA-256 hash over
the sorted file contents is computed and used as a cache key, so re-running the
pipeline on an unchanged codebase replays cached agent outputs instead of re-invoking
the model.

The Analyzer's output is a typed `AnalyzerOutput` record --- codebase statistics,
graph nodes and edges, hotspots, external dependencies, and cycles --- validated by
schema, with no language model involved in its construction.

### Service Boundary Identification

The Architect converts the directed dependency graph into an undirected weighted
graph, using edge confidence as the weight, and applies the Louvain community
detection algorithm \cite{kalia2021mono2micro} with a fixed random seed. Each
resulting community becomes a candidate service. The service name is derived
deterministically from the community's constituent modules (the two
alphabetically-first module names), with a numeric suffix appended on collision so
that distinct communities never produce colliding service identifiers. Each candidate
is emitted as a `ServiceBoundary` record: name, bounded-context description, member
modules, proposed endpoints, a confidence score, and a short rationale.

Optionally, the Architect prompts the model with the analysis summary and retrieved
domain-driven-design guidance to refine or re-group the communities; when the model
returns a well-formed set of boundaries these are used, otherwise the pipeline falls
back to the raw community assignment. Because the fallback is deterministic and
seed-fixed, the same input codebase yields the same decomposition on every run ---
a property that hosted, non-deterministic pipelines cannot offer
\cite{chen2026mono2sls}. ALMS trades the decomposition quality of learned or
trace-based methods \cite{sellami2025monoembed, kalia2021mono2micro} for this
determinism and for requiring neither training data, a GPU, nor runtime
instrumentation.

### Retrieval-Augmented Generation

Every LLM stage is grounded in a local knowledge base of migration patterns:
short curated documents grouped into categories for refactoring, FastAPI, DDD,
security, and testing. At initialisation the documents are split into
500-character chunks with 100-character overlap, embedded with a local embedding
model, and stored in a persistent on-disk vector index using cosine similarity. Each
agent is bound to the subset of categories relevant to its task --- the Analyzer to
refactoring patterns, the Architect to DDD patterns, the Refactoring agent to FastAPI
and security patterns, the Test-Gen agent to testing patterns --- and retrieves up to
three chunks per query, filtered by a 0.70 cosine-similarity threshold. The retriever returns
raw chunks for prompt injection and performs no model synthesis of its own, mirroring
the retriever-only design used elsewhere \cite{zan2023apicoder, chen2026mono2sls}.
Because the model is small and its training coverage of current framework idioms is
limited, this retrieval step substitutes for knowledge the model does not reliably
possess \cite{zan2023apicoder}. Embedding failures raise rather than silently
returning a zero vector, so a degraded knowledge base cannot pass unnoticed.

### Code Generation and the Compile--Retry Loop

For each proposed service the Refactoring agent receives the service's member
modules with **full function bodies** (unlike the Analyzer, which sees only
AST-level summaries), the target framework, and retrieved FastAPI and security
patterns, and emits one or more Python files implementing the service as a FastAPI
application with Pydantic schemas and SQLAlchemy models. Generated code is formatted
with `black` and `isort` and then passed through a `py_compile` gate. If compilation
fails, the orchestrator loops back to the Refactoring agent with the error, for up to
three attempts (configurable). If the service still does not compile after the last
attempt, it is marked as needing human review and carried forward with that status
rather than dropped. The retry loop is a genuine cycle in the execution graph
(Fig.~\ref{fig:statemachine}), and its firing rate is one of the properties measured
in the Evaluation. This staged
generate--check--regenerate structure is what allows a small model's first-attempt
errors to be recovered automatically instead of surfacing as broken output
\cite{chen2026mono2sls}.

### Test Generation and Shadow Testing

For each service that compiles, the Test-Gen agent generates a `pytest` suite ---
happy-path, error-path, and property-based (`hypothesis`) cases --- from the
generated service code and the corresponding legacy source. In addition, ALMS
includes a shadow-testing engine that runs identical inputs through a legacy callable
and its generated counterpart and compares outputs for exact match, recording any
discrepancies. This targets behavioural parity, the aspect of migration that
decomposition-only approaches do not address \cite{kalia2021mono2micro,
sellami2025monoembed} and that a separate line of work tackles for the test artefact
specifically \cite{yeh2024testmigration}. The shadow harness is currently exercised
against in-process callables; wiring it to the running container stack is future
work.

### Orchestration: Fan-out, Reducers, and Human Gates

The pipeline is a stateful graph. After boundary approval, the orchestrator issues
one parallel branch per proposed service; each branch runs the compile--retry loop
and then test generation as an isolated subgraph with its own attempt counter
(Fig.~\ref{fig:statemachine}). Branch results are merged back into a single list by a
custom reducer keyed on service name, so that parallel branches never race and a
re-run after a rejected final gate replaces a service's result rather than
duplicating it.

Three human-in-the-loop gates punctuate the pipeline: after analysis, after boundary
proposal, and after test generation. At each gate a reviewer may approve (continue),
reject with feedback (re-run the preceding stage with that feedback), or stop
(terminate). A command-line flag auto-approves every gate for unattended runs. These
gates make the decomposition and the generated output auditable checkpoints rather
than opaque end-to-end steps, which matters for the enterprise-migration setting that
automated pipelines target \cite{kalia2021mono2micro}.

### Output: Deployable Artifacts

On completion the orchestrator writes, per service, the generated Python module(s), a
`requirements.txt`, and a `Dockerfile`; a top-level `docker-compose.yml` wires the
services on distinct ports; and the generated test suites plus the analysis and
architecture records are serialised as JSON. The serialiser guarantees that every
directory referenced by the compose file contains an importable application entry
point --- the generated module if it defines one, a re-export shim if the entry point
is in a sibling module, or a minimal bootable stub otherwise, with any stubbed
services recorded in the run summary. The result is a portable container stack that
builds and runs with `docker compose`, with no dependency on a specific cloud
provider --- in contrast to pipelines that target a single vendor's serverless
platform \cite{chen2026mono2sls} (Table~\ref{tab:related}).
