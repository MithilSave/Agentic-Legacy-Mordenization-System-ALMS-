"""
Agents — Analyzer Agent
=========================
Codebase parsing & AST analysis using Ollama (qwen2.5-coder:7b).
Per CONTEXT.md §9 / IMPLEMENTATION_PLAN_v2.md §3:
- AST-only extraction via tools/code_analysis.py
- Ollama call with format="json", num_ctx=4096, temperature=0.05
- RAG retrieval scoped to refactoring_patterns, top_k=3
- Pydantic validation of output
- DiskCache keyed on codebase SHA-256
"""

import json
import logging
from typing import Dict, Any, Optional

import ollama as ollama_client

from core.config import Config
from core.constants import (
    AnalyzerOutput, GraphNode, GraphEdge, CouplingHotspot,
    CodebaseStats, ANALYZER_SYSTEM_PROMPT, Severity, EdgeType
)
from tools.code_analysis import (
    extract_code_structure, build_dependency_graph,
    find_circular_dependencies, find_coupling_hotspots,
    compute_codebase_hash, graph_to_dict, get_external_dependencies
)
from rag.retriever import AgentRetriever
from storage.cache import CacheManager

logger = logging.getLogger("agents.analyzer")


class AnalyzerAgent:
    """Codebase Analyzer Agent.

    Parses legacy monolithic code using AST analysis, builds a
    dependency graph, identifies coupling hotspots, and uses
    the LLM to produce structured insights.

    The AST pre-filter is wired ONLY here — this is the #1 listed
    pitfall in CONTEXT.md §15.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        retriever: Optional[AgentRetriever] = None,
        cache: Optional[CacheManager] = None,
    ):
        self.config = config or Config()
        self.retriever = retriever
        self.cache = cache
        self.agent_config = self.config.get_agent_config("analyzer")

    def analyze(self, source_path: str) -> AnalyzerOutput:
        """Run full analysis on a codebase.

        Args:
            source_path: Path to the monolithic codebase

        Returns:
            AnalyzerOutput with validated dependency graph
        """
        logger.info(f"═══ ANALYZER AGENT: Starting analysis of {source_path} ═══")

        # ── Check cache ──
        codebase_hash = compute_codebase_hash(source_path)
        if self.cache:
            cached = self.cache.get(f"analyzer:{codebase_hash}")
            if cached:
                logger.info("Cache hit — returning cached analysis")
                return AnalyzerOutput.model_validate_json(cached)

        # ── Step 1: AST Extraction ──
        logger.info("Step 1: Extracting code structure via AST...")
        code_structure = extract_code_structure(source_path)

        # ── Step 2: Build Dependency Graph ──
        logger.info("Step 2: Building dependency graph...")
        graph = build_dependency_graph(code_structure)

        # ── Step 3: Find Issues ──
        logger.info("Step 3: Detecting circular dependencies and hotspots...")
        cycles = find_circular_dependencies(graph)
        hotspots = find_coupling_hotspots(graph)
        external_deps = get_external_dependencies(code_structure)

        # ── Step 4: Prepare graph data ──
        graph_dict = graph_to_dict(graph)

        # ── Step 5: Prepare stats ──
        stats = CodebaseStats(
            total_files=code_structure["stats"]["total_files"],
            total_lines=code_structure["stats"]["total_lines"],
            total_functions=code_structure["stats"]["total_functions"],
            total_classes=code_structure["stats"]["total_classes"],
        )

        # Calculate average complexity
        complexities = [f.get("complexity", 1) for f in code_structure["functions"]]
        if complexities:
            stats.cyclomatic_complexity_avg = round(sum(complexities) / len(complexities), 2)

        # ── Step 6: RAG Context Retrieval ──
        rag_context = ""
        if self.retriever:
            logger.info("Step 6: Retrieving RAG context...")
            description = f"Monolith with {stats.total_files} files, {stats.total_functions} functions"
            rag_context = self.retriever.retrieve_for_analyzer(description)

        # ── Step 7: LLM Analysis ──
        logger.info("Step 7: Calling LLM for enhanced analysis...")
        llm_insights = self._call_llm(code_structure, graph_dict, stats, hotspots, rag_context)

        # ── Step 8: Build Validated Output ──
        logger.info("Step 8: Validating output with Pydantic...")
        output = self._build_output(stats, graph_dict, hotspots, cycles, external_deps, llm_insights)

        # ── Cache result ──
        if self.cache:
            self.cache.set(f"analyzer:{codebase_hash}", output.model_dump_json())

        logger.info(f"═══ ANALYZER AGENT: Complete — {len(output.nodes)} nodes, "
                     f"{len(output.edges)} edges, {len(output.hotspots)} hotspots ═══")
        return output

    def _call_llm(
        self,
        code_structure: Dict,
        graph_dict: Dict,
        stats: CodebaseStats,
        hotspots: list,
        rag_context: str,
    ) -> Dict[str, Any]:
        """Call Ollama for LLM-enhanced analysis."""
        # Build a summary of the code structure for the prompt
        code_summary = self._build_code_summary(code_structure)

        prompt = ANALYZER_SYSTEM_PROMPT.format(
            rag_context=rag_context or "No patterns retrieved.",
            codebase_stats=stats.model_dump_json(indent=2),
            code_structure=code_summary,
        )

        try:
            response = ollama_client.chat(
                model=self.config.ollama_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": (
                        "Analyze this codebase and provide structured insights. "
                        "Return JSON with: additional_hotspots (list), "
                        "anti_patterns (list of strings), "
                        "recommendations (list of strings), "
                        "overall_complexity_rating (LOW/MEDIUM/HIGH)."
                    )},
                ],
                format="json",
                options={
                    "num_ctx": self.agent_config["num_ctx"],
                    "temperature": self.agent_config["temperature"],
                },
            )

            content = response.get("message", {}).get("content", "{}")
            return json.loads(content)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {}

    def _build_code_summary(self, code_structure: Dict) -> str:
        """Build a concise code summary for the LLM prompt.

        Only includes structural info (AST pre-filter) — NO function bodies.
        This is the key difference from Refactoring/Test-Gen agents.
        """
        lines = []

        for module in code_structure["modules"]:
            lines.append(f"\n=== Module: {module['name']} ({module['file']}) ===")

            for func in module["functions"]:
                params = ", ".join(func.get("parameters", []))
                lines.append(
                    f"  def {func['name']}({params}) "
                    f"[complexity={func.get('complexity', '?')}, loc={func.get('loc', '?')}]"
                )
                if func.get("calls"):
                    lines.append(f"    calls: {', '.join(func['calls'][:10])}")

            for cls in module["classes"]:
                lines.append(f"  class {cls['name']}({', '.join(cls.get('bases', []))})")
                if cls.get("methods"):
                    lines.append(f"    methods: {', '.join(cls['methods'])}")

            for imp in module["imports"]:
                if imp["type"] == "from_import":
                    lines.append(f"  from {imp.get('from_module', '?')} import {imp.get('name', '?')}")

            for glob in module["globals"]:
                lines.append(f"  GLOBAL: {glob['name']}")

        return "\n".join(lines)

    def _build_output(
        self,
        stats: CodebaseStats,
        graph_dict: Dict,
        hotspots: list,
        cycles: list,
        external_deps: list,
        llm_insights: Dict,
    ) -> AnalyzerOutput:
        """Build the validated AnalyzerOutput from all analysis results."""
        # Convert graph nodes
        nodes = []
        for node in graph_dict.get("nodes", []):
            nodes.append(GraphNode(
                id=node["id"],
                type=node.get("type", "function"),
                module=node.get("module", node["id"].split(".")[0] if "." in node["id"] else "unknown"),
                metrics={
                    "complexity": node.get("complexity", 1),
                    "loc": node.get("loc", 0),
                    "parameters": node.get("parameters", 0),
                },
            ))

        # Convert graph edges
        edges = []
        for edge in graph_dict.get("edges", []):
            edge_type = edge.get("type", "internal_call")
            try:
                edge_type_enum = EdgeType(edge_type)
            except ValueError:
                edge_type_enum = EdgeType.INTERNAL_CALL

            edges.append(GraphEdge(
                source=edge["source"],
                target=edge["target"],
                type=edge_type_enum,
                confidence=edge.get("confidence", 0.9),
            ))

        # Convert hotspots
        validated_hotspots = []
        for hs in hotspots:
            try:
                severity = Severity(hs.get("severity", "MEDIUM"))
            except ValueError:
                severity = Severity.MEDIUM

            validated_hotspots.append(CouplingHotspot(
                module=hs["module"],
                coupled_to=hs.get("coupled_to", []),
                severity=severity,
                reason=hs.get("reason", ""),
            ))

        # Add LLM-identified hotspots
        for hs in llm_insights.get("additional_hotspots", []):
            if isinstance(hs, dict) and "module" in hs:
                validated_hotspots.append(CouplingHotspot(
                    module=hs["module"],
                    coupled_to=hs.get("coupled_to", []),
                    severity=Severity.MEDIUM,
                    reason=hs.get("reason", "LLM-identified"),
                ))

        return AnalyzerOutput(
            codebase_stats=stats,
            nodes=nodes,
            edges=edges,
            hotspots=validated_hotspots,
            external_dependencies=external_deps,
            circular_dependencies=[{"cycle": c} for c in cycles],
        )
