# tests/core/test_constants.py
import sys
sys.path.insert(0, ".")

from core.constants import ServiceUnit, PipelineState, ServiceBoundary


def test_service_unit_defaults():
    unit = ServiceUnit(service=ServiceBoundary(name="user-service", bounded_context="Users"))
    assert unit.compile_attempts == 0
    assert unit.needs_human_review is False
    assert unit.status == "pending"
    assert unit.refactoring_output is None
    assert unit.test_gen_output is None


def test_pipeline_state_service_units_default_empty():
    state = PipelineState(project_id="p1", source_path="/tmp/x")
    assert state.service_units == []
    assert state.dependency_review_approved is False
