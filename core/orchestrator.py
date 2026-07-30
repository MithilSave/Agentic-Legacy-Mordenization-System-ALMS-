"""
Core — Pipeline Orchestrator (LangGraph Implementation)
=======================================================
State machine implementing the migration pipeline:
Analyze → Architect → [HITL] → Refactor → TestGen → [HITL] → Done

Uses LangGraph for state management, enabling cyclic recovery loops.
"""

import json
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, TypedDict, List, Annotated

# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from core.config import Config
from core.constants import (
    PipelineState, AgentPhase, AnalyzerOutput, ArchitectOutput,
    ServiceUnit, ServiceBoundary, RefactoringOutput,
)
from agents.analyzer_agent import AnalyzerAgent
from agents.architect_agent import ArchitectAgent
from agents.refactoring_agent import RefactoringAgent
from agents.test_gen_agent import TestGenAgent
from rag.vector_store import VectorStore
from rag.retriever import AgentRetriever
from storage.cache import CacheManager
from storage.audit_logger import AuditLogger

logger = logging.getLogger("core.orchestrator")


def route_after_hitl(approved: bool, feedback: str) -> str:
    """Decide graph routing from a HITL decision.

    Returns 'approve', 'fail' (feedback is a stop keyword), or 'reject'.
    """
    if approved:
        return "approve"
    if feedback.strip().lower() in ("quit", "exit", "stop", "fail"):
        return "fail"
    return "reject"


def next_compile_action(compile_attempts: int, passed: bool, max_attempts: int = 3) -> str:
    """Decide what to do after a py_compile validation attempt.

    Returns 'pass' (move to test-gen), 'retry' (loop back to refactor),
    or 'needs_review' (exhausted retries, flag for a human).
    """
    if passed:
        return "pass"
    if compile_attempts < max_attempts:
        return "retry"
    return "needs_review"


def _replace_by_service_name(existing: list, updates: list) -> list:
    """Reducer for the `service_units` graph channel.

    Merges by `service.name` instead of concatenating (unlike `operator.add`):
    each parallel Send branch contributes exactly one entry per service, and
    if the human rejects the final gate and the fan-out re-runs, the new
    result replaces the old one for that service instead of duplicating it.
    """
    merged = {u.service.name: u for u in existing}
    for u in updates:
        merged[u.service.name] = u
    return list(merged.values())


class GraphState(TypedDict):
    """The state channels for LangGraph.

    `state` uses default (replace) semantics. `service_units` uses the
    `_replace_by_service_name` reducer so parallel branches can merge their
    results into a single list without race conditions or duplicates.
    """
    state: PipelineState
    service_units: Annotated[List[ServiceUnit], _replace_by_service_name]


class ServiceBranchState(TypedDict):
    """Local state for the per-service fan-out subgraph."""
    pipeline_state: PipelineState
    service_units: Annotated[List[ServiceUnit], _replace_by_service_name]
    branch_service: ServiceBoundary
    branch_compile_attempts: int
    branch_refactoring_output: Optional[RefactoringOutput]
    branch_last_error: Optional[str]


class PipelineOrchestrator:
    """Multi-agent pipeline orchestrator using LangGraph.

    Manages the stateful workflow:
    1. ANALYZING   — Analyzer Agent parses codebase
    2. ARCHITECTING — Architect Agent proposes boundaries
    3. [HITL]      — Human approves architecture (Cyclic loop on rejection)
    4. REFACTORING — Refactoring Agent generates FastAPI code
    5. TESTING     — Test-Gen Agent creates test suites
    6. [HITL]      — Human reviews final output
    7. COMPLETE    — Pipeline finished
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        ui_callback: Optional[Callable] = None,
    ):
        self.config = config or Config()
        self.ui_callback = ui_callback

        # Initialize infrastructure
        self.vector_store = VectorStore(self.config)
        self.retriever = AgentRetriever(self.vector_store, self.config)
        self.cache = CacheManager(self.config)
        self.audit = AuditLogger(self.config)

        # Initialize agents
        self.analyzer = AnalyzerAgent(self.config, self.retriever, self.cache)
        self.architect = ArchitectAgent(self.config, self.retriever)
        self.refactoring = RefactoringAgent(self.config, self.retriever)
        self.test_gen = TestGenAgent(self.config, self.retriever)

        # Pipeline state
        self.state = PipelineState()
        
        # Build LangGraph
        self.graph = self._build_graph()

    def _build_service_graph(self):
        """Build the subgraph that executes for each proposed service in parallel."""
        builder = StateGraph(ServiceBranchState)
        
        builder.add_node("refactor_service", self._node_refactor_service)
        builder.add_node("validate_service", self._node_validate_service)
        builder.add_node("mark_needs_review", self._node_mark_needs_review)
        builder.add_node("test_gen_service", self._node_test_gen_service)
        
        builder.add_edge(START, "refactor_service")
        builder.add_edge("refactor_service", "validate_service")
        
        builder.add_conditional_edges(
            "validate_service",
            self._route_validate_service,
            {
                "retry": "refactor_service",
                "needs_review": "mark_needs_review",
                "pass": "test_gen_service",
            },
        )
        builder.add_edge("mark_needs_review", END)
        builder.add_edge("test_gen_service", END)
        
        return builder.compile()

    def _build_graph(self):
        builder = StateGraph(GraphState)

        builder.add_node("analyze", self._node_analyze)
        builder.add_node("hitl_analyze", self._node_hitl_analyze)
        builder.add_node("architect", self._node_architect)
        builder.add_node("hitl_architect", self._node_hitl_architect)
        
        # Subgraph node for parallel fan-out
        service_subgraph = self._build_service_graph()
        builder.add_node("process_service", service_subgraph)
        
        builder.add_node("join", self._node_join)

        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "hitl_analyze")

        builder.add_conditional_edges(
            "hitl_analyze",
            self._route_hitl_analyze,
            {"approve": "architect", "reject": "analyze", "fail": END},
        )

        builder.add_edge("architect", "hitl_architect")

        def _route_after_architect_hitl(gstate: GraphState):
            state = gstate["state"]
            approved = getattr(state, "_last_hitl_approved", True)
            feedback = state.human_approvals[-1].get("feedback", "") if state.human_approvals else ""
            route = route_after_hitl(approved, feedback)
            if route == "fail":
                state.current_phase = AgentPhase.FAILED
                self._emit("pipeline_rejected", {"checkpoint": "after_architect"})
                return END
            if route == "reject":
                return "architect"
            return self._dispatch_refactor_sends(state)

        builder.add_conditional_edges(
            "hitl_architect",
            _route_after_architect_hitl,
            ["architect", "process_service", END],
        )

        builder.add_edge("process_service", "join")

        builder.add_node("hitl_final", self._node_hitl_final)
        builder.add_edge("join", "hitl_final")
        builder.add_conditional_edges(
            "hitl_final",
            self._route_hitl_final,
            ["process_service", END],
        )

        return builder.compile()

    def run(
        self,
        source_path: str,
        project_id: Optional[str] = None,
        skip_hitl: bool = False,
    ) -> PipelineState:
        """Run the complete migration pipeline via LangGraph."""
        self.state = PipelineState(
            project_id=project_id or str(uuid.uuid4())[:8],
            source_path=source_path,
        )

        self._load_source_code(source_path)
        self.run_id = self.audit.start_pipeline_run(self.state.project_id, source_path)
        
        # Save flag for HITL nodes dynamically on the model 
        self.state._skip_hitl = skip_hitl 

        self._emit("pipeline_start", {
            "project_id": self.state.project_id,
            "source_path": source_path,
            "files": len(self.state.source_code),
        })

        try:
            # Execute LangGraph workflow
            final_state = self.graph.invoke({
                "state": self.state,
                "service_units": [],
            })
            self.state = final_state["state"]

            if self.state.current_phase != AgentPhase.FAILED:
                self.state.current_phase = AgentPhase.COMPLETE
                total_tests = sum(
                    u.test_gen_output.total_tests for u in self.state.service_units if u.test_gen_output
                )
                self._emit("pipeline_complete", {
                    "services": len(self.state.service_units),
                    "tests": total_tests,
                })

                self.audit.complete_pipeline_run(
                    self.run_id, "completed",
                    services=len(self.state.service_units),
                    tests=total_tests,
                )
        except Exception as e:
            self.state.current_phase = AgentPhase.FAILED
            self.state.errors.append(str(e))
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            self.audit.complete_pipeline_run(self.run_id, "failed", summary=str(e))
            self._emit("pipeline_error", {"error": str(e)})

        return self.state

    # ──────────────────────────────────────────────
    # Graph Nodes
    # ──────────────────────────────────────────────

    def _node_analyze(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        state.current_phase = AgentPhase.ANALYZING
        self._emit("phase_start", {"phase": "analyzing", "agent": "Analyzer"})

        start = time.time()
        try:
            state.analyzer_output = self.analyzer.analyze(state.source_path)
            duration = int((time.time() - start) * 1000)

            self.audit.log_agent_action(
                "analyzer", "Codebase analysis complete",
                phase="analyzing",
                details={
                    "nodes": len(state.analyzer_output.nodes),
                    "edges": len(state.analyzer_output.edges),
                    "hotspots": len(state.analyzer_output.hotspots),
                },
                duration_ms=duration,
            )

            self._emit("phase_complete", {
                "phase": "analyzing",
                "nodes": len(state.analyzer_output.nodes),
                "edges": len(state.analyzer_output.edges),
                "hotspots": len(state.analyzer_output.hotspots),
                "duration_ms": duration,
            })
        except Exception as e:
            self.audit.log_agent_action("analyzer", "Analysis failed", success=False, error_message=str(e))
            raise

        return {"state": state}

    def _node_architect(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        state.current_phase = AgentPhase.ARCHITECTING
        self._emit("phase_start", {"phase": "architecting", "agent": "Architect"})

        start = time.time()
        try:
            state.architect_output = self.architect.design_architecture(state.analyzer_output)
            duration = int((time.time() - start) * 1000)

            self.audit.log_agent_action(
                "architect", "Architecture design complete",
                phase="architecting",
                details={"services": len(state.architect_output.proposed_services)},
                duration_ms=duration,
            )

            self._emit("phase_complete", {
                "phase": "architecting",
                "services": len(state.architect_output.proposed_services),
                "duration_ms": duration,
            })
        except Exception as e:
            self.audit.log_agent_action("architect", "Architecture design failed", success=False, error_message=str(e))
            raise

        return {"state": state}

    def _node_hitl_analyze(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        if getattr(state, "_skip_hitl", False):
            state._last_hitl_approved = True
            state.dependency_review_approved = True
            return {"state": state}

        approved = self._hitl_checkpoint("after_analyze", state.analyzer_output, state)
        state._last_hitl_approved = approved
        state.dependency_review_approved = approved
        return {"state": state}

    def _route_hitl_analyze(self, gstate: GraphState) -> str:
        state = gstate["state"]
        approved = getattr(state, "_last_hitl_approved", True)
        feedback = state.human_approvals[-1].get("feedback", "") if state.human_approvals else ""
        route = route_after_hitl(approved, feedback)
        if route == "fail":
            state.current_phase = AgentPhase.FAILED
            self._emit("pipeline_rejected", {"checkpoint": "after_analyze"})
        return route

    def _node_hitl_architect(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        if getattr(state, "_skip_hitl", False):
            state._last_hitl_approved = True
            return {"state": state}

        approved = self._hitl_checkpoint("after_architect", state.architect_output, state)
        state._last_hitl_approved = approved
        return {"state": state}

    def _dispatch_refactor_sends(self, state: PipelineState) -> list:
        """One Send per proposed service, each starting a fresh retry counter."""
        return [
            Send("process_service", {
                "pipeline_state": state,
                "branch_service": svc,
                "branch_compile_attempts": 0,
                "branch_refactoring_output": None,
                "branch_last_error": None,
            })
            for svc in state.architect_output.proposed_services
        ]

    def _node_refactor_service(self, gstate: ServiceBranchState) -> Dict[str, Any]:
        state = gstate["pipeline_state"]
        service = gstate["branch_service"]
        attempts = gstate["branch_compile_attempts"] + 1

        self._emit("refactoring_service", {"service": service.name, "attempt": attempts})
        start = time.time()
        try:
            output = self.refactoring.refactor_service(service, state.source_code)
        except Exception as e:
            logger.error(f"Refactoring failed for {service.name}: {e}")
            self.audit.log_agent_action(
                "refactoring", f"{service.name} raised an exception",
                phase="refactoring", success=False, error_message=str(e),
            )
            return {
                "branch_service": service,
                "branch_compile_attempts": attempts,
                "branch_refactoring_output": None,
                "branch_last_error": str(e),
            }

        duration = int((time.time() - start) * 1000)
        self.audit.log_agent_action(
            "refactoring", f"Generated {service.name} (attempt {attempts})",
            phase="refactoring", duration_ms=duration,
            details={"py_compile_passed": output.py_compile_passed},
        )
        return {
            "branch_service": service,
            "branch_compile_attempts": attempts,
            "branch_refactoring_output": output,
            "branch_last_error": None,
        }

    def _node_validate_service(self, gstate: ServiceBranchState) -> Dict[str, Any]:
        # No-op node: the routing decision happens in _route_validate_service.
        # Present as its own node (rather than folded into refactor_service)
        # so the retry loop is visible as a distinct graph edge.
        return {}

    def _route_validate_service(self, gstate: ServiceBranchState) -> str:
        output = gstate["branch_refactoring_output"]
        passed = bool(output) and output.py_compile_passed
        action = next_compile_action(
            gstate["branch_compile_attempts"],
            passed,
            self.config.max_retries,
        )
        return action

    def _node_mark_needs_review(self, gstate: ServiceBranchState) -> Dict[str, Any]:
        service = gstate["branch_service"]
        unit = ServiceUnit(
            service=service,
            refactoring_output=gstate["branch_refactoring_output"],
            compile_attempts=gstate["branch_compile_attempts"],
            needs_human_review=True,
            status="failed",
        )
        self.audit.log_agent_action(
            "refactoring", f"{service.name} exceeded retry limit ({gstate['branch_compile_attempts']} attempts)",
            phase="refactoring", success=False,
            error_message=gstate.get("branch_last_error") or "py_compile failed repeatedly",
        )
        # Since this node is in a subgraph, returning {"service_units": [unit]}
        # makes the subgraph's output contain that key, which LangGraph then 
        # forwards to the parent graph's reducer.
        return {"service_units": [unit]}

    def _node_test_gen_service(self, gstate: ServiceBranchState) -> Dict[str, Any]:
        state = gstate["pipeline_state"]
        service = gstate["branch_service"]
        refactoring_output = gstate["branch_refactoring_output"]

        start = time.time()
        try:
            test_output = self.test_gen.generate_tests(refactoring_output, state.source_code)
        except Exception as e:
            logger.error(f"Test generation failed for {service.name}: {e}")
            self.audit.log_agent_action(
                "test_gen", f"{service.name} test generation raised an exception",
                phase="testing", success=False, error_message=str(e),
            )
            unit = ServiceUnit(
                service=service,
                refactoring_output=refactoring_output,
                compile_attempts=gstate["branch_compile_attempts"],
                needs_human_review=True,
                status="failed",
            )
            return {"service_units": [unit]}

        duration = int((time.time() - start) * 1000)
        self.audit.log_agent_action(
            "test_gen", f"Generated tests for {service.name}",
            phase="testing", duration_ms=duration,
            details={"tests": test_output.total_tests},
        )
        unit = ServiceUnit(
            service=service,
            refactoring_output=refactoring_output,
            test_gen_output=test_output,
            compile_attempts=gstate["branch_compile_attempts"],
            needs_human_review=False,
            status="done",
        )
        return {"service_units": [unit]}

    def _node_join(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        state.service_units = gstate["service_units"]
        state.current_phase = AgentPhase.TESTING
        total_tests = sum(
            u.test_gen_output.total_tests for u in state.service_units if u.test_gen_output
        )
        self._emit("phase_complete", {
            "phase": "testing",
            "services_processed": len(state.service_units),
            "tests_generated": total_tests,
        })
        return {"state": state}

    def _node_hitl_final(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        if getattr(state, "_skip_hitl", False):
            state._last_hitl_approved = True
            return {"state": state}

        approved = self._hitl_checkpoint("after_test_gen", state.service_units, state)
        state._last_hitl_approved = approved
        return {"state": state}

    def _route_hitl_final(self, gstate: GraphState):
        state = gstate["state"]
        approved = getattr(state, "_last_hitl_approved", True)
        feedback = state.human_approvals[-1].get("feedback", "") if state.human_approvals else ""
        route = route_after_hitl(approved, feedback)
        if route == "fail":
            state.current_phase = AgentPhase.FAILED
            self._emit("pipeline_rejected", {"checkpoint": "after_test_gen"})
            return END
        if route == "approve":
            return END
        return self._dispatch_refactor_sends(state)
    # ──────────────────────────────────────────────
    # HITL Utilities
    # ──────────────────────────────────────────────

    def _hitl_checkpoint(self, checkpoint_name: str, output: Any, state: PipelineState) -> bool:
        state.iteration_count += 1

        if self.ui_callback:
            result = self.ui_callback("hitl_checkpoint", {
                "checkpoint": checkpoint_name,
                "iteration": state.iteration_count,
                "output": output,
            })
            approved = result.get("approved", True) if isinstance(result, dict) else bool(result)
            feedback = result.get("feedback", "") if isinstance(result, dict) else ""
        else:
            approved, feedback = self._cli_approval(checkpoint_name)

        self.audit.log_hitl_decision(
            checkpoint=checkpoint_name,
            approved=approved,
            feedback=feedback,
            iteration=state.iteration_count,
        )

        state.human_approvals.append({
            "checkpoint": checkpoint_name,
            "approved": approved,
            "feedback": feedback,
            "iteration": state.iteration_count,
        })
        return approved

    def _cli_approval(self, checkpoint_name: str) -> tuple:
        print(f"\n{'═' * 50}")
        print(f"  HITL CHECKPOINT: {checkpoint_name}")
        print(f"{'═' * 50}")
        response = input("  Approve? (y/n): ").strip().lower()
        approved = response in ("y", "yes", "")
        feedback = ""
        if not approved:
            feedback = input("  Feedback: ").strip()
        return approved, feedback

    # ──────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────

    def _load_source_code(self, source_path: str):
        path = Path(source_path)
        if path.is_file():
            self.state.source_code[path.name] = path.read_text(encoding="utf-8", errors="replace")
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                rel_path = str(py_file.relative_to(path))
                self.state.source_code[rel_path] = py_file.read_text(encoding="utf-8", errors="replace")
        else:
            raise ValueError(f"Source path does not exist: {source_path}")
        logger.info(f"Loaded {len(self.state.source_code)} source files")

    def _emit(self, event: str, data: Dict[str, Any] = None):
        if self.ui_callback:
            try:
                self.ui_callback(event, data or {})
            except Exception as e:
                logger.warning(f"UI callback error: {e}")

    def get_state(self) -> Dict[str, Any]:
        return self.state.model_dump()

    def cleanup(self):
        self.cache.close()
        self.audit.close()
