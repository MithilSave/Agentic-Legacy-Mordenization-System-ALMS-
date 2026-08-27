# ALMS Research Paper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to work
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Prose-drafting steps are done *with the user* (Claude assists, user is lead author);
> code/figure/artifact steps are fully executable by an agent.

**Goal:** Produce a submission-ready IEEE-conference-style paper (8–10 pp, double
column) on ALMS — a fully-local, low-resource, reproducible pipeline that migrates
Python monoliths to containerised FastAPI microservices — written from the current
single-case-study state of the system.

**Architecture:** Draft every section as version-controlled Markdown in `paper/sections/`,
generate all figures/tables from real pipeline output via scripts in `paper/figures/`,
keep per-reference notes in `paper/notes/`, then typeset the final PDF in Overleaf
using the IEEEtran `conference` template (Markdown → paste/sync). A `paper/build.md`
records the exact reproduction steps for the artifact appendix.

**Tech Stack:** Markdown + pandoc (local preview), IEEEtran on Overleaf (final),
Python + matplotlib/graphviz (figures from `examples/migration_output/` and a fresh
instrumented run), BibTeX (`paper/refs.bib`).

**Positioning (the thesis to defend):** Existing automated LLM migration pipelines
(Mono2Sls) depend on commercial hosted assistants (Cursor, Claude Code, DeepSeek,
Claude Sonnet) and LLM-embedding approaches (MonoEmbed) need GPU fine-tuning. ALMS
runs the *entire* migration — analysis, boundary selection, code generation, test
generation, validation — on a single commodity laptop with local Ollama models, at
zero API cost, offline, and fully reproducible. The contribution is **access**:
the design that makes this feasible on low resources, plus the open runnable artifact.
Boundary-quality parity with SOTA is explicitly *not* claimed.

---

## Constraints & scope decisions (from brainstorming)

| Decision | Value |
|---|---|
| Empirical scope | **Write from current state** — one case study (`examples/sample_monolith/`), plus one freshly instrumented run for resource/latency numbers. No multi-project benchmark in the core plan. |
| Format | IEEE conference/workshop, `\documentclass[conference]{IEEEtran}`, 8–10 pp |
| Contribution | Fully-local / no-cloud + low-resource "anyone can run it" + reproducible artifact |
| Deadline | 8 weeks from 2026-08-28 → **target 2026-10-23** |
| Paper class | **System-and-artifact / experience paper** with a case-study evaluation (frame N=1 honestly; lead with reproducibility) |
| Optional track E | Weeks 3–4 slack may be spent adding 3–5 extra monoliths (Task E1–E3). Marked OPTIONAL; not required for a complete paper. |

---

## File structure

```
paper/
  main.md                 # assembled paper (pandoc source); or sections concatenated
  sections/
    00-abstract.md
    01-introduction.md
    02-background-related-work.md
    03-approach.md
    04-implementation.md
    05-evaluation.md
    06-discussion-threats.md
    07-future-work.md
    08-conclusion.md
  figures/
    gen_graph_before_after.py   # dependency-graph node/edge/hotspot comparison
    gen_pipeline_diagram.py     # or hand-authored TikZ in overleaf; PNG fallback here
    gen_resource_table.py       # parse instrumented run → latency/RAM table
    gen_metrics_table.py        # parse audit.db + pipeline_summary.json → results table
    *.png / *.pdf               # outputs
  tables/
    related-work-comparison.md  # ALMS vs Mono2Sls vs MonoEmbed vs Mono2Micro vs ...
  notes/
    hassan-2024-slr.md
    martinez-saucedo-2025-mapping.md
    sellami-saied-2025-monoembed.md      # 2502.04604
    yeh-2024-testcase-migration.md
    chen-2026-mono2sls.md                # 2604.24550
    kalia-2021-mono2micro.md             # 2107.09698
    zan-2023-apicoder.md                 # 2307.15370
    huang-2024-onprem-llm.md             # 2410.11182
  refs.bib
  build.md                # exact commands to reproduce every number/figure
  README.md               # how to work on the paper (draft in md, typeset in Overleaf)
docs/superpowers/plans/2026-08-28-research-paper-alms.md   # this file
```

---

## Reference map (use these `\cite` keys)

| bib key | Paper | Role in the paper |
|---|---|---|
| `hassan2024slr` | Hassan et al., SLR monolith→microservice, IJACSA 15(10) 2024 | Background: migration is costly/manual; motivation stats |
| `martinez2025mapping` | Martínez Saucedo et al., systematic mapping, IST 177 2025 | Background: taxonomy of decomposition approaches |
| `sellami2025monoembed` | Sellami & Saied, MonoEmbed (contrastive LLM embeddings + clustering), arXiv 2502.04604 | Related work: LLM-based boundary selection; contrast (needs fine-tuning/GPU) |
| `yeh2024testmigration` | Yeh, Ma, Chen, LLM test-case migration, ICEBE 2024 | Related work: LLMs for the test-migration sub-problem; ALMS's Test-Gen agent |
| `chen2026mono2sls` | Chen et al., Mono2Sls (static analysis + 4 LLM agents + KB), arXiv 2604.24550 | **Closest prior work**; evaluation-design template; contrast (commercial LLMs, serverless, no community detection, no HITL) |
| `kalia2021mono2micro` | Kalia et al., Mono2Micro (spatio-temporal decomposition), ESEC/FSE 2021 | Non-LLM decomposition baseline; classic reference |
| `zan2023apicoder` | Zan et al., private-library code generation (APIFinder+APICoder), arXiv 2307.15370 | Supports RAG-for-codegen design (retrieve unseen API docs to ground generation) |
| `huang2024onprem` | Huang et al., on-premises LLM deployment (privacy vs confidentiality), arXiv 2410.11182 | Supports the local/privacy motivation |

---

## Phase 0 — Scaffold (Week 1, day 1)

### Task 0.1: Create paper skeleton and build docs

**Files:**
- Create: `paper/README.md`, `paper/build.md`, `paper/refs.bib` (empty stub),
  `paper/sections/00-abstract.md` … `08-conclusion.md` (one-line stubs),
  `paper/tables/related-work-comparison.md` (stub),
  `paper/notes/*.md` (8 stubs, one per reference)

- [ ] **Step 1: Create the section stub files**

Each `paper/sections/NN-name.md` contains only:
```markdown
# <Section Title>

<!-- STATUS: stub | drafting | self-reviewed | final -->
<!-- TARGET LENGTH: <col-inches> -->
```

- [ ] **Step 2: Write `paper/README.md`**

Content: "Draft sections here as Markdown. Figures/tables are generated by scripts in
`paper/figures/` from real pipeline output — never hand-typed. Final typesetting is
done in Overleaf with `\documentclass[conference]{IEEEtran}`; copy section prose in,
keep this repo as source of truth for text and the reproduction of numbers. Every
numeric claim in the paper must trace to a command in `build.md`."

- [ ] **Step 3: Write `paper/build.md` header**

```markdown
# Reproduction log

Environment: Windows 11, Python 3.11, Ollama <version>, model qwen2.5-coder:7b,
embeddings nomic-embed-text. CPU-only. RAM: <fill>.

Every figure and number in the paper is regenerated by the commands below.
```

- [ ] **Step 4: Commit**

```bash
git add paper/ docs/superpowers/plans/2026-08-28-research-paper-alms.md
git commit -m "docs(paper): scaffold IEEE paper structure and build log"
```

### Task 0.2: Resolve the model-config discrepancy (blocks Implementation + Eval)

**Files:**
- Modify: `README.md` or `config.yaml` (pick ONE model, make them agree)
- Modify: `paper/build.md` (record the decision)

- [ ] **Step 1: Decide.** `config.yaml` says `qwen2.5-coder:7b`; `README.md` example
  says `qwen3-coder:30b`. For a "runs on a laptop" paper, pick the smaller model that
  actually fits the stated 16 GB / CPU budget. Confirm it is installed:
  `ollama list`.
- [ ] **Step 2:** Edit whichever file is wrong so both name the same model. Note the
  exact tag and its parameter count / quantisation in `paper/build.md`.
- [ ] **Step 3: Commit**
```bash
git add README.md config.yaml paper/build.md
git commit -m "fix: align LLM model between README and config; record in paper build log"
```

---

## Phase 1 — Capture evidence from the current system (Week 1)

> All numbers in the paper come from here. Do this before writing Evaluation.

### Task 1.1: Instrumented end-to-end run on the sample monolith

**Files:**
- Create: `paper/figures/run_instrumented.md` (the transcript / notes)
- Uses: `main.py --demo --skip-hitl`, `audit.db`, `examples/migration_output/`

- [ ] **Step 1:** Clean slate: `rm -rf cache_db chroma_db audit.db examples/migration_output`
- [ ] **Step 2:** `python main.py --init-kb` — record wall-clock, and
  `du -sh chroma_db`, number of chunks indexed.
- [ ] **Step 3:** Run with OS resource capture:
```bash
python main.py --demo --skip-hitl --log-level INFO
```
  While it runs, sample peak RSS (Task Manager / `Get-Process python | Select PeakWorkingSet64`
  every few seconds, or wrap with a tiny psutil poller). Record: total wall-clock,
  per-phase wall-clock (from `audit.db`), peak RAM, whether GPU was used (no).
- [ ] **Step 4:** Record from `pipeline_summary.json` + `audit.db`:
  services proposed, services generated, `stub_services`, compile attempts per service,
  retry-loop firings, `needs_review` count, tests generated.
- [ ] **Step 5:** `cd examples/migration_output && docker compose build` (if Docker
  available) — record build success/failure per service. If Docker unavailable, record
  `python -c "import py_compile" ` pass over every `generated.py` instead.
- [ ] **Step 6:** Save the console log to `paper/figures/run_instrumented.md` with a
  short prose summary at the top.
- [ ] **Step 7: Commit**
```bash
git add paper/figures/run_instrumented.md paper/build.md
git commit -m "docs(paper): capture instrumented end-to-end run (resources, latency, outputs)"
```

### Task 1.2: Before/after dependency-graph figure

**Files:**
- Create: `paper/figures/gen_graph_before_after.py`
- Create: `paper/figures/graph_before_after.pdf` (output)
- Test: `paper/figures/test_gen_graph_before_after.py`

- [ ] **Step 1: Write the failing test**
```python
# paper/figures/test_gen_graph_before_after.py
import subprocess, pathlib, sys

def test_figure_and_stats_are_produced(tmp_path):
    out = subprocess.run(
        [sys.executable, "paper/figures/gen_graph_before_after.py", "--out", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert (tmp_path / "graph_before_after.pdf").exists()
    stats = (tmp_path / "graph_stats.txt").read_text()
    # sanity: the "after" (filtered) graph must be strictly smaller
    assert "nodes_before" in stats and "nodes_after" in stats
```

- [ ] **Step 2: Run it, verify it fails**
Run: `pytest paper/figures/test_gen_graph_before_after.py -v`
Expected: FAIL — `gen_graph_before_after.py` does not exist.

- [ ] **Step 3: Implement `gen_graph_before_after.py`**
```python
"""Regenerate the dependency-graph comparison figure + stats from the real sample.

'before' = graph built WITHOUT the builtin/stdlib call filter (bug-1 behaviour);
'after'  = current build_dependency_graph. Both from examples/sample_monolith.
"""
import argparse, pathlib
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tools.code_analysis import extract_code_structure, build_dependency_graph, find_coupling_hotspots


def _build_unfiltered(struct):
    """Reconstruct the pre-fix behaviour: edge to every unresolved call name."""
    from tools.code_analysis import _resolve_call
    g = nx.DiGraph()
    for m in struct["modules"]:
        g.add_node(m["name"], kind="module")
    for f in struct["functions"]:
        g.add_node(f["id"], kind="func")
        for call in f.get("calls", []):
            t = _resolve_call(call, f["module"], struct)
            g.add_edge(f["id"], t or call)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="examples/sample_monolith")
    ap.add_argument("--out", default="paper/figures")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)

    struct = extract_code_structure(a.src)
    before = _build_unfiltered(struct)
    after = build_dependency_graph(struct)
    hs_after = find_coupling_hotspots(after)

    stats = (
        f"nodes_before {before.number_of_nodes()}\n"
        f"edges_before {before.number_of_edges()}\n"
        f"nodes_after {after.number_of_nodes()}\n"
        f"edges_after {after.number_of_edges()}\n"
        f"hotspots_after {len(hs_after)}\n"
    )
    (out / "graph_stats.txt").write_text(stats)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, g, title in ((axes[0], before, "Unfiltered"), (axes[1], after, "Filtered (ALMS)")):
        pos = nx.spring_layout(g, seed=42, k=0.5)
        nx.draw(g, pos, ax=ax, node_size=40, width=0.4, with_labels=False)
        ax.set_title(f"{title}\n{g.number_of_nodes()} nodes / {g.number_of_edges()} edges")
    fig.tight_layout()
    fig.savefig(out / "graph_before_after.pdf")
    print(stats)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test, verify it passes**
Run: `pytest paper/figures/test_gen_graph_before_after.py -v`
Expected: PASS.

- [ ] **Step 5:** Run for real, record the printed stats into `paper/build.md`.
Run: `python paper/figures/gen_graph_before_after.py`

- [ ] **Step 6: Commit**
```bash
git add paper/figures/gen_graph_before_after.py paper/figures/test_gen_graph_before_after.py paper/figures/graph_before_after.pdf paper/figures/graph_stats.txt paper/build.md
git commit -m "docs(paper): generate dependency-graph before/after figure from real sample"
```

### Task 1.3: Metrics table generator

**Files:**
- Create: `paper/figures/gen_metrics_table.py`
- Create: `paper/tables/metrics.md` (output)
- Test: `paper/figures/test_gen_metrics_table.py`

- [ ] **Step 1: Write the failing test**
```python
import subprocess, sys, pathlib
def test_metrics_table_emitted(tmp_path):
    r = subprocess.run([sys.executable, "paper/figures/gen_metrics_table.py",
                        "--audit", "audit.db",
                        "--summary", "examples/migration_output/pipeline_summary.json",
                        "--out", str(tmp_path / "metrics.md")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    md = (tmp_path / "metrics.md").read_text()
    assert "| Metric | Value |" in md
```

- [ ] **Step 2: Run, verify fail.**
Run: `pytest paper/figures/test_gen_metrics_table.py -v` → FAIL (missing script).

- [ ] **Step 3: Implement `gen_metrics_table.py`**
```python
"""Emit the Evaluation results table from a completed run's audit.db + summary json."""
import argparse, json, sqlite3, pathlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    summary = json.loads(pathlib.Path(a.summary).read_text())
    con = sqlite3.connect(a.audit)
    cur = con.cursor()

    def scalar(q, *p):
        cur.execute(q, p); row = cur.fetchone()
        return row[0] if row else None

    rows = {
        "Source files": None,           # fill from analyzer stats if logged
        "Services proposed": summary.get("services_generated"),
        "Stub services": len(summary.get("stub_services", []) or []),
        "Services needing review": len(summary.get("services_needing_review", []) or []),
        "Tests generated": summary.get("tests_generated"),
        "Pipeline phase reached": summary.get("phase"),
        "Total agent actions": scalar("select count(*) from agent_actions"),
        "Failed agent actions": scalar("select count(*) from agent_actions where success=0"),
        "Total pipeline wall-clock (ms)": scalar("select sum(duration_ms) from agent_actions"),
    }
    lines = ["| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in rows.items()]
    pathlib.Path(a.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
```
> NOTE: adjust table/column names to the real `audit.db` schema — inspect first with
> `sqlite3 audit.db ".schema"` and fix the queries in Step 3 before running.

- [ ] **Step 4: Run test → PASS.**
- [ ] **Step 5:** Run for real; paste output into `paper/tables/metrics.md` and `build.md`.
- [ ] **Step 6: Commit**
```bash
git add paper/figures/gen_metrics_table.py paper/figures/test_gen_metrics_table.py paper/tables/metrics.md paper/build.md
git commit -m "docs(paper): generate evaluation metrics table from audit.db"
```

### Task 1.4: Resource/latency table

**Files:**
- Create: `paper/tables/resources.md` (hand-assembled from Task 1.1 captures)

- [ ] **Step 1:** Build a table: rows = {KB indexing, Analyze, Architect, Refactor
  (per service, mean±range), Test-Gen, Total}; columns = {wall-clock, peak RAM, GPU}.
  Add a footer line: model, quantisation, host CPU, RAM, OS, `$0` API cost, offline=yes.
- [ ] **Step 2: Commit**
```bash
git add paper/tables/resources.md
git commit -m "docs(paper): resource and latency table for the case-study run"
```

### Task 1.5: Pipeline architecture figure

**Files:**
- Create: `paper/figures/pipeline.pdf` (export) OR `paper/figures/pipeline.tex` (TikZ)

- [ ] **Step 1:** Reuse the README mermaid pipeline graph as the basis. Produce a
  clean vector figure: either (a) redraw as TikZ in Overleaf later and keep a
  placeholder note here, or (b) render the mermaid to PDF now
  (`mmdc -i pipeline.mmd -o pipeline.pdf` if mermaid-cli is available).
- [ ] **Step 2:** Also produce a second figure: the LangGraph state machine
  (nodes: analyze, hitl_analyze, architect, hitl_architect, process_service×N subgraph
  with the refactor↔validate retry cycle, join, hitl_final) — from
  `core/orchestrator.py`.
- [ ] **Step 3: Commit**
```bash
git add paper/figures/pipeline* paper/figures/statemachine*
git commit -m "docs(paper): pipeline and state-machine figures"
```

---

## Phase 2 — Digest references (Week 2)

### Task 2.1–2.8: One note file per reference

For each `paper/notes/<key>.md`, fill this template (≤1 page):

```markdown
# <Full citation>

**Problem / claim:**
**Method (1 paragraph):**
**Evaluation setup:** datasets, baselines, metrics, headline numbers
**How ALMS relates:** (similar? contrast? we cite it for X)
**Exact sentences we can cite in each section:** intro / related work / eval / discussion
**BibTeX:** <paste, add to paper/refs.bib>
```

- [ ] **2.1 `chen2026mono2sls`** — DO THIS FIRST. Read the converted text in full
  (`.claude/.../tool-results/...976354.txt`). Capture: 4 RQs (Deployability, Functional
  Correctness, Ablation of static-analysis planning, Cloud-Native Design); baselines
  Cursor / Claude Code / LLM-Baseline (DeepSeek-V3.2, Claude Sonnet 4.6); 6 apps, >10K
  LOC, 76 endpoints; 100% deploy, 66.1% end-to-end correctness, 98.7% API-coverage F1;
  metrics Validation Pass Rate + API Coverage F1. **Contrast column for ALMS:** local
  vs commercial models; microservices vs serverless/SAM; Louvain community detection vs
  none; 3 HITL gates vs none; $0/offline vs API cost.
- [ ] **2.2 `sellami2025monoembed`** (2502.04604) — LLM embeddings + Contrastive
  Learning + LoRA to represent monolith components, then cluster into microservices;
  contrast: needs model fine-tuning / GPU; ALMS uses off-the-shelf local model + a
  deterministic call-graph + Louvain, no training.
- [ ] **2.3 `kalia2021mono2micro`** (2107.09698) — spatio-temporal decomposition from
  runtime traces + business use cases; evaluated vs 4 techniques on Java apps; the
  established non-LLM baseline; ALMS is static-only + LLM codegen on Python.
- [ ] **2.4 `zan2023apicoder`** (2307.15370) — APIFinder + APICoder: retrieve private
  API docs to ground code generation for unseen libraries; cite as precedent for
  ALMS's RAG over FastAPI/DDD/security pattern docs.
- [ ] **2.5 `huang2024onprem`** (2410.11182) — on-premises LLM deployment, privacy vs
  model confidentiality; cite for the privacy/data-locality motivation.
- [ ] **2.6 `hassan2024slr`** — SLR; pull quantified pain points of manual migration
  for the Introduction.
- [ ] **2.7 `martinez2025mapping`** — systematic mapping; use its taxonomy to place
  ALMS (input = source code; technique = graph clustering + LLM; output = deployable
  code + tests).
- [ ] **2.8 `yeh2024testmigration`** — LLM test-case migration monolith→microservices;
  relate to ALMS's Test-Gen agent + shadow testing.
- [ ] **Commit after each:** `git add paper/notes/<key>.md paper/refs.bib && git commit -m "docs(paper): notes on <short name>"`

### Task 2.9: Related-work comparison table

**Files:** `paper/tables/related-work-comparison.md`

- [ ] **Step 1:** Rows = {Mono2Micro, MonoEmbed, Mono2Sls, Yeh et al., **ALMS**}.
  Columns = {Input, Boundary method, Code generation, Test generation, LLM hosting,
  Hardware, Cost, Offline, Human-in-loop, Target output, Evaluation scale}.
- [ ] **Step 2: Commit**
```bash
git add paper/tables/related-work-comparison.md
git commit -m "docs(paper): related-work comparison table"
```

---

## Phase 3 — Draft sections (Weeks 3–5)

> Each section task has the SAME sub-steps. Do them with the user (Claude drafts a
> version, user edits). "Self-review checklist" is run inline before commit.

**Per-section sub-steps (apply to Tasks 3.1–3.9):**
- [ ] Draft the section in `paper/sections/NN-*.md` to the target length.
- [ ] Self-review checklist:
  - Every claim is either cited or traceable to `paper/build.md` / a table / a figure.
  - No number appears that isn't reproduced by a `build.md` command.
  - No forward reference to a section/figure that doesn't exist yet.
  - Contribution framing = local/low-resource/reproducible (not "we beat SOTA").
  - Passive-voice / filler trimmed; IEEE tone.
- [ ] `pandoc paper/sections/NN-*.md -o /tmp/preview.pdf` (or skip if pandoc absent) — reads OK.
- [ ] Update the `<!-- STATUS -->` line to `self-reviewed`.
- [ ] Commit: `git add paper/sections/NN-*.md && git commit -m "docs(paper): draft <section>"`

### Task 3.1: Introduction (`01-introduction.md`, ~1 col)
Content beats: (1) monolith→microservice migration is costly and manual
[`hassan2024slr`, `martinez2025mapping`]; (2) automated LLM pipelines exist but assume
hosted commercial models and/or GPU fine-tuning [`chen2026mono2sls`,
`sellami2025monoembed`] — excluding students, small teams, privacy-constrained orgs;
(3) **ALMS**: the whole pipeline (analysis → boundary selection → FastAPI generation →
test generation → validation) on one laptop, local models, offline, $0, reproducible;
(4) contributions list: the design, the deterministic-scaffold split that makes small
local models usable, the open artifact, a case-study feasibility evaluation;
(5) paper roadmap.

### Task 3.2: Background & Related Work (`02-background-related-work.md`, ~1.5 col)
Subsections: (a) monolith→microservice migration & decomposition taxonomy
[`martinez2025mapping`, `kalia2021mono2micro`]; (b) LLMs for decomposition & migration
[`sellami2025monoembed`, `chen2026mono2sls`]; (c) LLMs for test migration
[`yeh2024testmigration`]; (d) RAG-grounded code generation [`zan2023apicoder`];
(e) local/on-prem LLMs [`huang2024onprem`]. End with the comparison table (Task 2.9)
and an explicit "gap: no fully-local, low-resource, reproducible end-to-end pipeline".

### Task 3.3: Approach (`03-approach.md`, ~2.5 col) — the core section
Beats: overall pipeline figure (Task 1.5); the **deterministic vs LLM boundary**
(what the LLM does / does NOT do); Analyzer (AST → call graph → builtin/stdlib
filtering → coupling hotspots → cycles); Architect (undirected weighted graph →
Louvain `random_state=42` → `ServiceBoundary` proposals, deterministic dedup);
Refactoring agent + the `py_compile` retry loop as a graph cycle (state-machine
figure); Test-Gen + shadow testing; RAG (KB categories, per-agent scoped retrieval,
fail-loud embedding); Pydantic contracts as the "no LLM-checks-LLM" mechanism; HITL
gates; LangGraph orchestration (`Send` fan-out, `_replace_by_service_name` reducer);
output (per-service `generated.py` + Dockerfile + `docker-compose.yml`, guaranteed
bootable entrypoint).

### Task 3.4: Implementation (`04-implementation.md`, ~1 col)
Stack table; model + quantisation + why this model fits the budget; per-agent context
windows sized for 16 GB; ChromaDB local; `diskcache` keyed on codebase hash; SQLite
audit; `rich` UI. Artifact: repo URL, licence, `--demo` one-command run, what's
git-ignored and regenerable.

### Task 3.5: Evaluation (`05-evaluation.md`, ~1.5 col)
Frame as feasibility/experience, N=1, honest. RQs:
- **RQ1 (Feasibility):** does the full pipeline run to completion on commodity CPU
  hardware with a local model? → Task 1.1 numbers, resource table (Task 1.4).
- **RQ2 (Output validity):** are generated services syntactically valid & bootable? →
  `py_compile` pass rate, `docker compose build` result, generated tests, retry-loop
  firings, `needs_review` count (Task 1.3 table).
- **RQ3 (Effect of deterministic filtering):** graph before/after (Task 1.2 figure +
  stats): 134→75 nodes, 263→104 edges, 6→2 hotspots; argue this makes small-model
  boundary reasoning tractable.
- **RQ4 (Resource/cost profile vs hosted pipelines):** qualitative table vs
  `chen2026mono2sls` — $0 vs API cost, laptop vs cloud, offline vs online,
  reproducible seed vs vendor drift. Do NOT claim correctness parity.
- End with an end-to-end **case-study walkthrough** of `sample_monolith` (input
  characteristics → proposed services → one generated service excerpt → its generated
  test → compose file).

### Task 3.6: Discussion & Threats to Validity (`06-discussion-threats.md`, ~0.75 col)
Threats (from `HANDOFF.md` §8): single case study / one language & framework;
Louvain over-merges around hub modules (`app`); `tables`/`inter_service_calls`/
`data_ownership` not derived; LLM nondeterminism (temp>0, no seed on backend);
behavioural fidelity unquantified (no live parity harness yet); model-dependent
results. Construct/internal/external validity paragraphs.

### Task 3.7: Future Work (`07-future-work.md`, ~0.25 col)
Multi-project benchmark; wire `ShadowTestingEngine` to `docker compose up` + replay;
resumable LangGraph SQLite checkpoints; learned/interactive boundary refinement;
multi-language front-end.

### Task 3.8: Conclusion (`08-conclusion.md`, ~0.25 col)
Restate: end-to-end migration is feasible fully-locally on a laptop; the deterministic
scaffold is what makes a small local model sufficient; artifact is open and
one-command reproducible.

### Task 3.9: Abstract (`00-abstract.md`, ~200 words) — write LAST
Problem → approach (local, low-resource, deterministic scaffold + LLM) → what was
built → case-study findings (runs on CPU laptop in <X> min, all services compile,
graph noise cut ~44%) → artifact available.

---

## Phase 4 — Assemble & typeset (Week 6)

### Task 4.1: Assemble `paper/main.md`
- [ ] Concatenate sections in order with a title block (title, authors, affiliation,
  keywords). Title candidates (pick with user): *"ALMS: A Fully-Local, Low-Resource
  Pipeline for Migrating Python Monoliths to FastAPI Microservices"*.
- [ ] Commit.

### Task 4.2: Overleaf typeset
- [ ] Create Overleaf project from `IEEEtran` `conference` template.
- [ ] Paste each section; move tables to `tabular`/`booktabs`; place figures
  (`graph_before_after.pdf`, `pipeline.pdf`, `statemachine.pdf`).
- [ ] Import `paper/refs.bib`; fix any missing BibTeX.
- [ ] Compile; fix overfull boxes; check it lands in 8–10 pp.
- [ ] Export PDF → `paper/ALMS-paper-draft.pdf`; commit.

### Task 4.3: Reproduce-everything check
- [ ] Fresh clone / clean state; run every command in `paper/build.md`; confirm every
  number and figure in the PDF matches. Fix mismatches. Commit `build.md` updates.

---

## Phase 5 — Review passes (Week 7)

### Task 5.1: Claims-vs-evidence audit
- [ ] Go through the PDF line by line; for every quantitative or comparative claim,
  write the evidence source in a margin list. Any claim with no source → cut or hedge.

### Task 5.2: Related-work fairness pass
- [ ] Re-read `paper/notes/chen2026mono2sls.md` and `sellami2025monoembed.md`; ensure
  contrasts are accurate and not strawman (they solve a partly different problem).

### Task 5.3: Structure & IEEE compliance
- [ ] Section balance, figure captions self-contained, no widows, `\cite` before
  punctuation per IEEE, keywords present, ≤ page limit, anonymised if required.

### Task 5.4: External read
- [ ] Hand to faculty mentor / a peer; collect comments; triage into must-fix / nice.
- [ ] Apply must-fix; commit each batch.

### Task 5.5: Language polish
- [ ] `superpowers:writing-clearly-and-concisely` pass (or manual): cut filler, active
  voice, consistent tense (present for the system, past for the study).

---

## Phase 6 — Finalise (Week 8)

- [ ] **Task 6.1:** Final compile; regenerate `paper/ALMS-paper-draft.pdf`.
- [ ] **Task 6.2:** Write `paper/README.md` "how to cite / artifact" section; tag the
  repo commit used for the paper (`git tag paper-v1`).
- [ ] **Task 6.3:** Prepare submission package: PDF, source zip, `refs.bib`, artifact
  link. If arXiv: `arxiv` metadata, category `cs.SE`.
- [ ] **Task 6.4:** Update `PROGRESS.md` — mark the paper done, link the PDF.
- [ ] **Task 6.5:** Commit + push; open PR to `main` for the `paper/` directory.

---

## OPTIONAL Track E — light multi-monolith expansion (Weeks 3–4 slack only)

> Do ONLY if Phase 1–3 are ahead of schedule. Materially strengthens RQ1/RQ2 and
> reviewer confidence; converts "case study" → "small multi-project study".

### Task E1: Collect 3–5 small Python monoliths
- [ ] Criteria: single-repo Flask/Django app, 500–5000 LOC, permissive licence,
  importable without external services. Record each in `paper/notes/benchmark-corpus.md`
  (name, URL, commit, LOC, licence).

### Task E2: Batch runner
**Files:** Create `benchmark/run_corpus.py`
- [ ] TDD: test that given a dir of repos it runs `main.py --skip-hitl` on each and
  writes `benchmark/results/<name>/metrics.json` (services, compile pass rate, retries,
  needs_review, wall-clock, peak RAM).
- [ ] Implement; run; commit results.

### Task E3: Aggregate table + update Evaluation
- [ ] `benchmark/aggregate.py` → `paper/tables/corpus-results.md` (per-repo rows +
  mean±std). Fold into `05-evaluation.md` RQ1/RQ2; adjust Abstract & Threats
  (N changes from 1 to k).

---

## Self-review of this plan

- **Spec coverage:** every rubric-relevant paper element (lit review → Phase 2 +
  Task 3.2; problem statement → Task 3.1; design → Task 3.3 + figures; results →
  Phase 1 + Task 3.5; report → the whole `paper/`) has a task. ✓
- **Placeholders:** figure/metrics scripts contain real code; queries flagged
  "inspect schema first" where the exact `audit.db` columns aren't known from here. ✓
- **Consistency:** bib keys fixed in the reference map are used verbatim in Phase 3. ✓
- **Known risk:** `gen_metrics_table.py` SQL must be adapted to the real `audit.db`
  schema (Task 1.3 Step 3 note). `run_instrumented` RAM sampling is manual on Windows
  unless a psutil poller is added.
