# tests/core/test_routing.py
import sys
sys.path.insert(0, ".")

from core.orchestrator import route_after_hitl, next_compile_action


def test_route_after_hitl_approved():
    assert route_after_hitl(True, "") == "approve"


def test_route_after_hitl_rejected_with_normal_feedback():
    assert route_after_hitl(False, "please add pagination") == "reject"


def test_route_after_hitl_rejected_with_stop_keyword():
    for word in ("quit", "exit", "stop", "fail", "QUIT", " Stop "):
        assert route_after_hitl(False, word) == "fail"


def test_next_compile_action_pass():
    assert next_compile_action(compile_attempts=1, passed=True) == "pass"


def test_next_compile_action_retry_below_max():
    assert next_compile_action(compile_attempts=1, passed=False, max_attempts=3) == "retry"
    assert next_compile_action(compile_attempts=2, passed=False, max_attempts=3) == "retry"


def test_next_compile_action_needs_review_at_max():
    assert next_compile_action(compile_attempts=3, passed=False, max_attempts=3) == "needs_review"
