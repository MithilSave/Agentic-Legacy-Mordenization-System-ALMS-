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
from typing import Dict, Any, Optional, Callable, TypedDict

# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, START, END

from core.config import Config
from core.constants import PipelineState, AgentPhase, AnalyzerOutput, ArchitectOutput
from agents.analyzer_agent import AnalyzerAgent
from agents.architect_agent import ArchitectAgent
from agents.refactoring_agent import RefactoringAgent
from agents.test_gen_agent import TestGenAgent
from rag.vector_store import VectorStore
from rag.retriever import AgentRetriever
from storage.cache import CacheManager
from storage.audit_logger import AuditLogger

logger = logging.getLogger("core.orchestrator")


class GraphState(TypedDict):
    """The state channel for LangGraph."""
    state: PipelineState


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

    def _build_graph(self):
        builder = StateGraph(GraphState)

        builder.add_node("analyze", self._node_analyze)
        builder.add_node("architect", self._node_architect)
        builder.add_node("hitl_architect", self._node_hitl_architect)
        builder.add_node("refactor", self._node_refactor)
        builder.add_node("test_gen", self._node_test_gen)
        builder.add_node("hitl_tests", self._node_hitl_tests)

        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "architect")
        builder.add_edge("architect", "hitl_architect")
        
        builder.add_conditional_edges(
            "hitl_architect",
            self._route_hitl_architect,
            {"approve": "refactor", "reject": "architect", "fail": END}
        )
        
        builder.add_edge("refactor", "test_gen")
        builder.add_edge("test_gen", "hitl_tests")
        
        builder.add_conditional_edges(
            "hitl_tests",
            self._route_hitl_tests,
            {"approve": END, "reject": "test_gen", "fail": END}
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
            final_state = self.graph.invoke({"state": self.state})
            self.state = final_state["state"]

            if self.state.current_phase != AgentPhase.FAILED:
                self.state.current_phase = AgentPhase.COMPLETE
                self._emit("pipeline_complete", {
                    "services": len(self.state.refactoring_outputs),
                    "tests": self.state.test_gen_output.total_tests if self.state.test_gen_output else 0,
                })

                self.audit.complete_pipeline_run(
                    self.run_id, "completed",
                    services=len(self.state.refactoring_outputs),
                    tests=self.state.test_gen_output.total_tests if self.state.test_gen_output else 0,
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

    def _node_hitl_architect(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        if getattr(state, "_skip_hitl", False):
            state._last_hitl_approved = True
            return {"state": state}

        approved = self._hitl_checkpoint("after_architect", state.architect_output, state)
        state._last_hitl_approved = approved
        return {"state": state}

    def _route_hitl_architect(self, gstate: GraphState) -> str:
        state = gstate["state"]
        if not getattr(state, "_last_hitl_approved", True):
            last_feedback = state.human_approvals[-1].get("feedback", "")
            if last_feedback.lower() in ("quit", "exit", "stop", "fail"):
                state.current_phase = AgentPhase.FAILED
                self._emit("pipeline_rejected", {"checkpoint": "after_architect"})
                return "fail"
            # Cycle back to architect to refine based on feedback
            return "reject"
        return "approve"

    def _node_refactor(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        state.current_phase = AgentPhase.REFACTORING
        self._emit("phase_start", {"phase": "refactoring", "agent": "Refactoring"})

        start = time.time()
        state.refactoring_outputs = []

        for i, service in enumerate(state.architect_output.proposed_services):
            self._emit("refactoring_service", {
                "service": service.name,
                "index": i + 1,
                "total": len(state.architect_output.proposed_services),
            })
            try:
                output = self.refactoring.refactor_service(service, state.source_code)
                state.refactoring_outputs.append(output)
            except Exception as e:
                logger.error(f"Refactoring failed for {service.name}: {e}")
                state.errors.append(f"Refactoring {service.name}: {e}")

        duration = int((time.time() - start) * 1000)
        self._emit("phase_complete", {
            "phase": "refactoring",
            "services_generated": len(state.refactoring_outputs),
            "duration_ms": duration,
        })
        return {"state": state}

    def _node_test_gen(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        state.current_phase = AgentPhase.TESTING
        self._emit("phase_start", {"phase": "testing", "agent": "Test-Gen"})

        start = time.time()
        if not state.refactoring_outputs:
            return {"state": state}
            
        first_output = state.refactoring_outputs[0]
        try:
            state.test_gen_output = self.test_gen.generate_tests(first_output, state.source_code)
            duration = int((time.time() - start) * 1000)
            self._emit("phase_complete", {
                "phase": "testing",
                "tests_generated": state.test_gen_output.total_tests,
                "duration_ms": duration,
            })
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            raise
        return {"state": state}

    def _node_hitl_tests(self, gstate: GraphState) -> GraphState:
        state = gstate["state"]
        if getattr(state, "_skip_hitl", False):
            state._last_hitl_approved = True
            return {"state": state}

        approved = self._hitl_checkpoint("after_test_gen", state.test_gen_output, state)
        state._last_hitl_approved = approved
        return {"state": state}

    def _route_hitl_tests(self, gstate: GraphState) -> str:
        state = gstate["state"]
        if not getattr(state, "_last_hitl_approved", True):
            last_feedback = state.human_approvals[-1].get("feedback", "")
            if last_feedback.lower() in ("quit", "exit", "stop", "fail"):
                state.current_phase = AgentPhase.FAILED
                self._emit("pipeline_rejected", {"checkpoint": "after_test_gen"})
                return "fail"
            return "reject"
        return "approve"


    # ──────────────────────────────────────────────
    # HITL Utilities
    # ──────────────────────────────────────────────

    def _hitl_checkpoint(self, checkpoint_name: str, output: Any, state: PipelineState) -> bool:
        self._emit("hitl_checkpoint", {"checkpoint": checkpoint_name})
        state.iteration_count += 1

        if self.ui_callback:
            result = self.ui_callback("hitl_approval", {
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
