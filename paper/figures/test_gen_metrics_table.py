"""Test the metrics-table generator against a synthetic audit.db + summary.

No real pipeline run (hence no Ollama) is required.
"""

import json
import pathlib
import sqlite3
import subprocess
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Schema copied from storage/audit_logger.py::_init_db
_SCHEMA = """
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, agent TEXT NOT NULL, action TEXT NOT NULL,
    phase TEXT, details TEXT, duration_ms INTEGER,
    success INTEGER DEFAULT 1, error_message TEXT
);
CREATE TABLE hitl_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, checkpoint TEXT NOT NULL, approved INTEGER NOT NULL,
    approver TEXT, feedback TEXT, iteration INTEGER DEFAULT 1
);
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL, source_path TEXT NOT NULL, started_at TEXT NOT NULL,
    completed_at TEXT, status TEXT DEFAULT 'running',
    services_generated INTEGER DEFAULT 0, tests_generated INTEGER DEFAULT 0, summary TEXT
);
"""


def _make_audit(path):
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    con.executemany(
        "INSERT INTO audit_log (timestamp, agent, action, phase, duration_ms, success) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("t", "analyzer", "done", "analyzing", 1200, 1),
            ("t", "architect", "done", "architecting", 800, 1),
            ("t", "refactoring", "gen user-service", "refactoring", 5000, 1),
            ("t", "refactoring", "gen order-service", "refactoring", 6000, 0),
            ("t", "test_gen", "done", "testing", 3000, 1),
        ],
    )
    con.executemany(
        "INSERT INTO hitl_decisions (timestamp, checkpoint, approved) VALUES (?,?,?)",
        [("t", "after_analyze", 1), ("t", "after_architect", 0)],
    )
    con.execute(
        "INSERT INTO pipeline_runs (project_id, source_path, started_at, completed_at, "
        "status, services_generated, tests_generated) VALUES (?,?,?,?,?,?,?)",
        ("abcd1234", "examples/sample_monolith", "t0", "t1", "completed", 3, 7),
    )
    con.commit()
    con.close()


def test_metrics_table_emitted(tmp_path):
    audit = tmp_path / "audit.db"
    summary = tmp_path / "pipeline_summary.json"
    out = tmp_path / "metrics.md"
    _make_audit(audit)
    summary.write_text(json.dumps({
        "source_path": "examples/sample_monolith",
        "phase": "complete",
        "services_generated": 3,
        "tests_generated": 7,
        "stub_services": ["order-service"],
        "services_needing_review": [],
        "errors": [],
    }))

    r = subprocess.run(
        [
            sys.executable, "paper/figures/gen_metrics_table.py",
            "--audit", str(audit), "--summary", str(summary), "--out", str(out),
        ],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    md = out.read_text()
    assert "| Metric | Value |" in md
    assert "| Services generated | 3 |" in md
    assert "| Stub services (no runnable code) | 1 |" in md
    assert "|   of which failed | 1 |" in md
    assert "|   rejections | 1 |" in md
    # per-phase breakdown present
    assert "| refactoring | 2 |" in md
