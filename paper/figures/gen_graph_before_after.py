"""Regenerate the dependency-graph comparison figure + stats from the real sample.

'before' = graph built the way ``build_dependency_graph`` did *before* the
           builtin/stdlib call filter (commit 59a97b0, "Bug 1"): an edge to every
           unresolved call name, plus inheritance edges to every base name.
'after'  = the current ``build_dependency_graph``.

Both are built from ``examples/sample_monolith`` with no LLM involved. The
node/edge/hotspot reduction is the evidence for the paper's RQ3 (deterministic
filtering makes the boundary-detection input tractable for a small local model).

Run from the repository root:

    python paper/figures/gen_graph_before_after.py [--src DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import networkx as nx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Ensure the repo root is importable when run from anywhere.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.code_analysis import (  # noqa: E402
    extract_code_structure,
    build_dependency_graph,
    find_coupling_hotspots,
    _resolve_call,
)


def build_unfiltered_graph(struct: dict) -> nx.DiGraph:
    """Reconstruct the pre-filter behaviour of build_dependency_graph."""
    g = nx.DiGraph()

    for module in struct["modules"]:
        g.add_node(module["name"], type="module")

    for func in struct["functions"]:
        g.add_node(func["id"], type=func["type"], module=func["module"])
        for call in func.get("calls", []):
            target = _resolve_call(call, func["module"], struct)
            if target:
                g.add_edge(func["id"], target, type="internal_call")
            else:
                # pre-fix: an edge to the raw call name (builtins, stdlib
                # methods, local-variable methods, ...) — this is the pollution
                g.add_edge(func["id"], call, type="external_call")

    for cls in struct["classes"]:
        g.add_node(cls["id"], type="class", module=cls["module"])
        for base in cls.get("bases", []):
            g.add_edge(cls["id"], base, type="inheritance")

    return g


def _summarise(g: nx.DiGraph) -> str:
    return f"{g.number_of_nodes()} nodes / {g.number_of_edges()} edges"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="examples/sample_monolith")
    ap.add_argument("--out", default="paper/figures")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    struct = extract_code_structure(args.src)
    before = build_unfiltered_graph(struct)
    after = build_dependency_graph(struct)

    hs_before = find_coupling_hotspots(before)
    hs_after = find_coupling_hotspots(after)

    stats = (
        f"source {args.src}\n"
        f"nodes_before {before.number_of_nodes()}\n"
        f"edges_before {before.number_of_edges()}\n"
        f"hotspots_before {len(hs_before)}\n"
        f"nodes_after {after.number_of_nodes()}\n"
        f"edges_after {after.number_of_edges()}\n"
        f"hotspots_after {len(hs_after)}\n"
        f"node_reduction_pct {100.0 * (before.number_of_nodes() - after.number_of_nodes()) / max(before.number_of_nodes(), 1):.1f}\n"
        f"edge_reduction_pct {100.0 * (before.number_of_edges() - after.number_of_edges()) / max(before.number_of_edges(), 1):.1f}\n"
    )
    (out / "graph_stats.txt").write_text(stats, encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, g, title in (
        (axes[0], before, "Unfiltered"),
        (axes[1], after, "Filtered (ALMS)"),
    ):
        pos = nx.spring_layout(g, seed=42, k=0.6)
        nx.draw(
            g, pos, ax=ax, node_size=45, width=0.4, arrowsize=5,
            node_color="#4477aa", edge_color="#999999", with_labels=False,
        )
        ax.set_title(f"{title}\n{_summarise(g)}", fontsize=10)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "graph_before_after.pdf")
    fig.savefig(out / "graph_before_after.png", dpi=150)

    print(stats, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
