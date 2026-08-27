import pathlib
import subprocess
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_figure_and_stats_are_produced(tmp_path):
    out = subprocess.run(
        [
            sys.executable,
            "paper/figures/gen_graph_before_after.py",
            "--out",
            str(tmp_path),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert (tmp_path / "graph_before_after.pdf").exists()
    stats = (tmp_path / "graph_stats.txt").read_text()

    vals = dict(line.split(maxsplit=1) for line in stats.strip().splitlines())
    nb, na = int(vals["nodes_before"]), int(vals["nodes_after"])
    eb, ea = int(vals["edges_before"]), int(vals["edges_after"])

    # The whole point: filtering removes non-code symbols, so the filtered
    # graph is strictly smaller on both nodes and edges.
    assert na < nb, f"filtered graph not smaller: {na} >= {nb}"
    assert ea < eb, f"filtered edges not fewer: {ea} >= {eb}"
    # And it must not collapse to nothing.
    assert na > 0 and ea > 0
