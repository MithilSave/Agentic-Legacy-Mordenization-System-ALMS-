# tests/storage/test_audit_logger_concurrency.py
import sys
import threading
sys.path.insert(0, ".")

from storage.audit_logger import AuditLogger


class FakeConfig:
    def __init__(self, db_path):
        self.audit_db_path = db_path


def test_concurrent_log_agent_action_no_errors(tmp_path):
    db_path = str(tmp_path / "audit_test.db")
    logger = AuditLogger(config=FakeConfig(db_path))
    errors = []

    def worker(i):
        try:
            logger.log_agent_action("refactoring", f"service-{i}", phase="refactoring")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    logs = logger.get_recent_logs(limit=50)
    assert len(logs) == 20
    logger.close()
