"""
Storage — SQLite Audit Logger
================================
Comprehensive audit trail for all agent actions and human decisions.
Per CONTEXT.md: SQLite, not PostgreSQL/ELK.
"""

import sqlite3
import threading
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.config import Config

logger = logging.getLogger("storage.audit")


class AuditLogger:
    """SQLite-backed audit logger for agent actions.

    Logs all agent executions, HITL decisions, errors,
    and system events for the capstone demo audit trail.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db_path = self.config.audit_db_path
        self._conn = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the audit database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                phase TEXT,
                details TEXT,
                duration_ms INTEGER,
                success INTEGER DEFAULT 1,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS hitl_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                checkpoint TEXT NOT NULL,
                approved INTEGER NOT NULL,
                approver TEXT,
                feedback TEXT,
                iteration INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'running',
                services_generated INTEGER DEFAULT 0,
                tests_generated INTEGER DEFAULT 0,
                summary TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log(agent);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        """)
        conn.commit()

    def _get_conn(self):
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def log_agent_action(
        self,
        agent: str,
        action: str,
        phase: str = "",
        details: Optional[Dict] = None,
        duration_ms: int = 0,
        success: bool = True,
        error_message: str = "",
    ):
        """Log an agent action.

        Args:
            agent: Agent name (analyzer, architect, refactoring, test_gen)
            action: Action description
            phase: Pipeline phase
            details: Additional details as dict
            duration_ms: Execution time in milliseconds
            success: Whether the action succeeded
            error_message: Error message if failed
        """
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO audit_log
                (timestamp, agent, action, phase, details, duration_ms, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    agent,
                    action,
                    phase,
                    json.dumps(details) if details else None,
                    duration_ms,
                    1 if success else 0,
                    error_message,
                )
            )
            conn.commit()

        # Also log to Python logger
        level = logging.INFO if success else logging.ERROR
        logger.log(level, f"[{agent}] {action} ({duration_ms}ms) {'✓' if success else '✗ ' + error_message}")

    def log_hitl_decision(
        self,
        checkpoint: str,
        approved: bool,
        approver: str = "user",
        feedback: str = "",
        iteration: int = 1,
    ):
        """Log a Human-in-the-Loop decision."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO hitl_decisions
                (timestamp, checkpoint, approved, approver, feedback, iteration)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    checkpoint,
                    1 if approved else 0,
                    approver,
                    feedback,
                    iteration,
                )
            )
            conn.commit()
        logger.info(f"[HITL] {checkpoint}: {'APPROVED' if approved else 'REJECTED'} by {approver}")

    def start_pipeline_run(self, project_id: str, source_path: str) -> int:
        """Record the start of a pipeline run. Returns run ID."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """INSERT INTO pipeline_runs (project_id, source_path, started_at)
                VALUES (?, ?, ?)""",
                (project_id, source_path, datetime.now().isoformat())
            )
            conn.commit()
            return cursor.lastrowid

    def complete_pipeline_run(
        self, run_id: int, status: str = "completed",
        services: int = 0, tests: int = 0, summary: str = ""
    ):
        """Record pipeline completion."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """UPDATE pipeline_runs
                SET completed_at = ?, status = ?, services_generated = ?,
                    tests_generated = ?, summary = ?
                WHERE id = ?""",
                (datetime.now().isoformat(), status, services, tests, summary, run_id)
            )
            conn.commit()

    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """Get recent audit log entries."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the audit trail."""
        conn = self._get_conn()

        total_actions = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        total_decisions = conn.execute("SELECT COUNT(*) FROM hitl_decisions").fetchone()[0]
        total_runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]

        agent_counts = {}
        for row in conn.execute("SELECT agent, COUNT(*) as cnt FROM audit_log GROUP BY agent").fetchall():
            agent_counts[row["agent"]] = row["cnt"]

        return {
            "total_actions": total_actions,
            "total_hitl_decisions": total_decisions,
            "total_pipeline_runs": total_runs,
            "actions_by_agent": agent_counts,
        }

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
