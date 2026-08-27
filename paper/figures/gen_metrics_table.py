"""Emit the Evaluation results table from a completed run.

Reads the SQLite audit trail (``audit.db``, schema in ``storage/audit_logger.py``)
and ``examples/migration_output/pipeline_summary.json``, writes a Markdown table.

Run from the repository root AFTER a pipeline run (partner task):

    python paper/figures/gen_metrics_table.py \
        --audit audit.db \
        --summary examples/migration_output/pipeline_summary.json \
        --out paper/tables/metrics.md
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3


def _scalar(cur: sqlite3.Cursor, query: str):
    try:
        cur.execute(query)
    except sqlite3.OperationalError:
        return None
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def collect(audit_path: str, summary_path: str) -> dict:
    summary = json.loads(pathlib.Path(summary_path).read_text(encoding="utf-8"))

    con = sqlite3.connect(audit_path)
    cur = con.cursor()

    total_ms = _scalar(cur, "SELECT SUM(duration_ms) FROM audit_log")
    per_phase = {}
    try:
        cur.execute(
            "SELECT phase, COUNT(*), COALESCE(SUM(duration_ms), 0) "
            "FROM audit_log GROUP BY phase ORDER BY phase"
        )
        per_phase = {p or "(none)": (n, ms) for p, n, ms in cur.fetchall()}
    except sqlite3.OperationalError:
        pass

    rows = {
        "Source path": summary.get("source_path"),
        "Pipeline phase reached": summary.get("phase"),
        "Services generated": summary.get("services_generated"),
        "Stub services (no runnable code)": len(summary.get("stub_services", []) or []),
        "Services needing human review": len(summary.get("services_needing_review", []) or []),
        "Tests generated": summary.get("tests_generated"),
        "Pipeline errors": len(summary.get("errors", []) or []),
        "Audit-logged agent actions": _scalar(cur, "SELECT COUNT(*) FROM audit_log"),
        "  of which failed": _scalar(cur, "SELECT COUNT(*) FROM audit_log WHERE success = 0"),
        "HITL decisions recorded": _scalar(cur, "SELECT COUNT(*) FROM hitl_decisions"),
        "  rejections": _scalar(cur, "SELECT COUNT(*) FROM hitl_decisions WHERE approved = 0"),
        "Total agent wall-clock (s)": round(total_ms / 1000.0, 1) if total_ms else None,
    }

    run_meta = {}
    try:
        cur.execute(
            "SELECT project_id, status, services_generated, tests_generated, "
            "started_at, completed_at FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        )
        r = cur.fetchone()
        if r:
            run_meta = {
                "project_id": r[0], "status": r[1],
                "started_at": r[4], "completed_at": r[5],
            }
    except sqlite3.OperationalError:
        pass

    con.close()
    return {"rows": rows, "per_phase": per_phase, "run_meta": run_meta}


def render(data: dict) -> str:
    out = ["| Metric | Value |", "|---|---|"]
    for k, v in data["rows"].items():
        out.append(f"| {k} | {'' if v is None else v} |")

    if data["per_phase"]:
        out += ["", "| Phase | Actions | Wall-clock (s) |", "|---|---|---|"]
        for phase, (n, ms) in data["per_phase"].items():
            out.append(f"| {phase} | {n} | {round(ms / 1000.0, 1)} |")

    if data["run_meta"]:
        out += ["", "```", json.dumps(data["run_meta"], indent=2), "```"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    md = render(collect(args.audit, args.summary))
    pathlib.Path(args.out).write_text(md, encoding="utf-8")
    print(md, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
