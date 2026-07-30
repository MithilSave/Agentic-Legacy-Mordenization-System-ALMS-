import sys
import uuid
import pytest
sys.path.insert(0, ".")

from core.orchestrator import PipelineOrchestrator
from core.constants import (
    AnalyzerOutput, ArchitectOutput, ServiceBoundary,
    RefactoringOutput, TestGenOutput
)
from core.config import Config


class FakeConfig:
    def __init__(self, tmp_path):
        self._config = {
            "audit": {"database": str(tmp_path / "audit.db")},
            "safety": {"max_retries": 3},
            "agents": {},
            "ollama": {"host": "", "model": "", "embedding_model": ""},
            "chromadb": {"persist_directory": str(tmp_path / "chroma"), "collection_name": "test"},
            "cache": {"directory": str(tmp_path / "cache"), "size_limit": 1000},
        }
        
    @property
    def audit_db_path(self): return self._config["audit"]["database"]
    
    @property
    def max_retries(self): return self._config["safety"]["max_retries"]
    
    @property
    def ollama_host(self): return ""
    @property
    def ollama_model(self): return ""
    @property
    def embedding_model(self): return ""
    @property
    def chromadb_persist_dir(self): return ""
    @property
    def chromadb_collection(self): return ""
    @property
    def cache_directory(self): return ""
    @property
    def cache_size_limit(self): return 1000
    
    def get_agent_config(self, name): return {}

class FakeAnalyzer:
    def __init__(self, *args, **kwargs): pass
    def analyze(self, source_path):
        return AnalyzerOutput(
            project_summary="test", 
            domain_models=[],
            nodes=[], edges=[], hotspots=[]
        )

class FakeArchitect:
    def __init__(self, *args, **kwargs): pass
    def design_architecture(self, analyzer_output):
        return ArchitectOutput(
            proposed_services=[
                ServiceBoundary(name="svc-flaky", bounded_context="Flaky"),
                ServiceBoundary(name="svc-solid", bounded_context="Solid"),
            ]
        )

class FakeRefactoring:
    def __init__(self, *args, **kwargs):
        self.attempts = {"svc-flaky": 0, "svc-solid": 0}
        
    def refactor_service(self, service, source_code):
        self.attempts[service.name] += 1
        
        # svc-solid always passes
        if service.name == "svc-solid":
            return RefactoringOutput(
                service_name=service.name,
                code="solid_code()",
                py_compile_passed=True
            )
            
        # svc-flaky fails twice, passes on 3rd attempt
        passed = self.attempts[service.name] >= 3
        return RefactoringOutput(
            service_name=service.name,
            code="flaky_code()",
            py_compile_passed=passed
        )

class FakeTestGen:
    def __init__(self, *args, **kwargs): pass
    def generate_tests(self, refactoring_output, source_code):
        return TestGenOutput(service_name=refactoring_output.service_name, test_cases=[], total_tests=5)


def test_fanout_and_retry_logic(tmp_path, monkeypatch):
    # Patch agent classes in orchestrator to use our fakes
    import core.orchestrator as orch
    monkeypatch.setattr(orch, "AnalyzerAgent", FakeAnalyzer)
    monkeypatch.setattr(orch, "ArchitectAgent", FakeArchitect)
    monkeypatch.setattr(orch, "RefactoringAgent", FakeRefactoring)
    monkeypatch.setattr(orch, "TestGenAgent", FakeTestGen)
    
    # Needs a real VectorStore stub if it tries to init it
    class FakeVectorStore:
        def __init__(self, *args, **kwargs): pass
    class FakeRetriever:
        def __init__(self, *args, **kwargs): pass
    class FakeCacheManager:
        def __init__(self, *args, **kwargs): pass
        
    monkeypatch.setattr(orch, "VectorStore", FakeVectorStore)
    monkeypatch.setattr(orch, "AgentRetriever", FakeRetriever)
    monkeypatch.setattr(orch, "CacheManager", FakeCacheManager)
    
    config = FakeConfig(tmp_path)
    orchestrator = PipelineOrchestrator(config=config)
    
    # Run the pipeline, skip HITL gates
    state = orchestrator.run(
        source_path=str(tmp_path),
        project_id="test-proj",
        skip_hitl=True
    )
    
    # Assertions
    assert len(state.service_units) == 2
    
    unit_flaky = next(u for u in state.service_units if u.service.name == "svc-flaky")
    unit_solid = next(u for u in state.service_units if u.service.name == "svc-solid")
    
    # svc-solid should pass immediately
    assert unit_solid.compile_attempts == 1
    assert unit_solid.status == "done"
    assert not unit_solid.needs_human_review
    assert unit_solid.test_gen_output.total_tests == 5
    
    # svc-flaky should take 3 attempts (initial attempt = 0 -> fails -> attempt 1 -> fails -> attempt 2 -> passes)
    # The attempts count in gstate is "previous attempts before this call", so
    # - call 1: compile_attempts=0, passes=False -> action=retry (calls with attempts=1)
    # - call 2: compile_attempts=1, passes=False -> action=retry (calls with attempts=2)
    # - call 3: compile_attempts=2, passes=True -> action=pass
    # The final unit.compile_attempts will be 3.
    assert unit_flaky.compile_attempts == 3
    assert unit_flaky.status == "done"
    assert not unit_flaky.needs_human_review
    assert unit_flaky.test_gen_output.total_tests == 5


def test_retry_limit_exhausted(tmp_path, monkeypatch):
    import core.orchestrator as orch
    monkeypatch.setattr(orch, "AnalyzerAgent", FakeAnalyzer)
    monkeypatch.setattr(orch, "ArchitectAgent", FakeArchitect)
    
    class FakeRefactoringAlwaysFails(FakeRefactoring):
        def refactor_service(self, service, source_code):
            return RefactoringOutput(
                service_name=service.name,
                code="bad_code()",
                py_compile_passed=False
            )
            
    monkeypatch.setattr(orch, "RefactoringAgent", FakeRefactoringAlwaysFails)
    monkeypatch.setattr(orch, "TestGenAgent", FakeTestGen)
    
    class FakeVectorStore:
        def __init__(self, *args, **kwargs): pass
    class FakeRetriever:
        def __init__(self, *args, **kwargs): pass
    class FakeCacheManager:
        def __init__(self, *args, **kwargs): pass
        
    monkeypatch.setattr(orch, "VectorStore", FakeVectorStore)
    monkeypatch.setattr(orch, "AgentRetriever", FakeRetriever)
    monkeypatch.setattr(orch, "CacheManager", FakeCacheManager)
    
    config = FakeConfig(tmp_path)
    orchestrator = PipelineOrchestrator(config=config)
    
    state = orchestrator.run(
        source_path=str(tmp_path),
        project_id="test-proj-2",
        skip_hitl=True
    )
    
    assert len(state.service_units) == 2
    for unit in state.service_units:
        # Both should exhaust retries and need review
        assert unit.status == "failed"
        assert unit.needs_human_review
        assert unit.compile_attempts == 3 # the max limit in config
        assert unit.test_gen_output is None
