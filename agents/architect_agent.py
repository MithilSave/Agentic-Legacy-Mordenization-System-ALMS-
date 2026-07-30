"""
Agents — Architect Agent
==========================
Domain-Driven Design microservice boundary proposals.
Uses Louvain clustering on the Analyzer's NetworkX graph.

Per IMPLEMENTATION_PLAN_v2.md §3:
- Louvain clustering on NetworkX graph
- RAG retrieval scoped to ddd_patterns, top_k=3
- Outputs ServiceBoundary Pydantic models with confidence scores
"""

import json
import logging
from typing import Dict, Any, Optional, List

import networkx as nx
import ollama as ollama_client

from core.config import Config
from core.constants import (
    ArchitectOutput, ServiceBoundary, ServiceEndpoint,
    InterServiceCall, AnalyzerOutput, ARCHITECT_SYSTEM_PROMPT
)
from rag.retriever import AgentRetriever

logger = logging.getLogger("agents.architect")


class ArchitectAgent:
    """Domain Architect Agent.

    Proposes logical microservice boundaries using:
    1. Louvain community detection on the dependency graph
    2. DDD patterns from RAG knowledge base
    3. LLM reasoning for refined boundary proposals
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        retriever: Optional[AgentRetriever] = None,
    ):
        self.config = config or Config()
        self.retriever = retriever
        self.agent_config = self.config.get_agent_config("architect")

    def design_architecture(self, analyzer_output: AnalyzerOutput) -> ArchitectOutput:
        """Propose microservice boundaries from the Analyzer's output.

        Args:
            analyzer_output: Validated output from the Analyzer Agent

        Returns:
            ArchitectOutput with proposed services and confidence scores
        """
        logger.info("═══ ARCHITECT AGENT: Starting architecture design ═══")

        # ── Step 1: Reconstruct NetworkX graph ──
        logger.info("Step 1: Reconstructing dependency graph...")
        graph = self._build_graph(analyzer_output)

        # ── Step 2: Louvain clustering ──
        logger.info("Step 2: Running Louvain community detection...")
        communities = self._detect_communities(graph)

        # ── Step 3: RAG retrieval ──
        rag_context = ""
        if self.retriever:
            logger.info("Step 3: Retrieving DDD patterns...")
            modules_summary = ", ".join(
                set(n.module for n in analyzer_output.nodes if n.module != "unknown")
            )
            rag_context = self.retriever.retrieve_for_architect(
                f"Modules: {modules_summary}. "
                f"Hotspots: {len(analyzer_output.hotspots)}. "
                f"Circular deps: {len(analyzer_output.circular_dependencies)}"
            )

        # ── Step 4: LLM-enhanced boundary proposals ──
        logger.info("Step 4: Calling LLM for architecture proposals...")
        llm_result = self._call_llm(analyzer_output, communities, rag_context)

        # ── Step 5: Build validated output ──
        logger.info("Step 5: Validating output with Pydantic...")
        output = self._build_output(communities, llm_result, analyzer_output)

        logger.info(f"═══ ARCHITECT AGENT: Complete — "
                     f"{len(output.proposed_services)} services proposed ═══")
        return output

    def _build_graph(self, analyzer_output: AnalyzerOutput) -> nx.Graph:
        """Reconstruct an undirected graph for community detection."""
        G = nx.Graph()

        for node in analyzer_output.nodes:
            G.add_node(node.id, module=node.module, type=node.type)

        for edge in analyzer_output.edges:
            # Use confidence as edge weight
            G.add_edge(edge.source, edge.target, weight=edge.confidence)

        return G

    def _detect_communities(self, graph: nx.Graph) -> Dict[str, int]:
        """Apply Louvain community detection.

        Returns mapping of node_id -> community_id
        """
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(graph, random_state=42)
            num_communities = len(set(partition.values()))
            logger.info(f"Louvain detected {num_communities} communities")
            return partition
        except ImportError:
            logger.warning("python-louvain not installed, falling back to module-based clustering")
            return self._fallback_clustering(graph)
        except Exception as e:
            logger.warning(f"Louvain failed: {e}, using fallback clustering")
            return self._fallback_clustering(graph)

    def _fallback_clustering(self, graph: nx.Graph) -> Dict[str, int]:
        """Simple module-based clustering as fallback."""
        partition = {}
        module_ids = {}
        counter = 0

        for node in graph.nodes():
            module = graph.nodes[node].get("module", "unknown")
            if module not in module_ids:
                module_ids[module] = counter
                counter += 1
            partition[node] = module_ids[module]

        return partition

    def _call_llm(
        self,
        analyzer_output: AnalyzerOutput,
        communities: Dict[str, int],
        rag_context: str,
    ) -> Dict[str, Any]:
        """Call Ollama for LLM-enhanced architecture proposals."""

        # Prepare dependency graph summary
        dep_summary = {
            "stats": analyzer_output.codebase_stats.model_dump(),
            "modules": list(set(n.module for n in analyzer_output.nodes)),
            "hotspots": [h.model_dump() for h in analyzer_output.hotspots],
            "circular_dependencies": analyzer_output.circular_dependencies,
            "communities": self._summarize_communities(communities),
            "external_dependencies": analyzer_output.external_dependencies,
        }

        prompt = ARCHITECT_SYSTEM_PROMPT.format(
            rag_ddd_patterns=rag_context or "No DDD patterns retrieved.",
            dependency_graph=json.dumps(dep_summary, indent=2, default=str),
        )

        try:
            response = ollama_client.chat(
                model=self.config.ollama_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": (
                        "Based on the dependency graph and community detection results, "
                        "propose microservice boundaries. Return JSON with: "
                        "proposed_services (list of {name, bounded_context, modules, tables, "
                        "endpoints, inter_service_calls, confidence_score, reason}), "
                        "inter_service_patterns (dict), data_ownership (dict)."
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

    def _summarize_communities(self, communities: Dict[str, int]) -> Dict[str, List[str]]:
        """Group nodes by their community for the LLM."""
        groups = {}
        for node_id, community_id in communities.items():
            key = f"community_{community_id}"
            if key not in groups:
                groups[key] = []
            groups[key].append(node_id)
        return groups

    def _build_output(
        self,
        communities: Dict[str, int],
        llm_result: Dict,
        analyzer_output: AnalyzerOutput,
    ) -> ArchitectOutput:
        """Build validated ArchitectOutput from analysis results."""
        proposed_services = []

        # Try to use LLM proposals first
        llm_services = llm_result.get("proposed_services", [])

        if llm_services:
            for svc in llm_services:
                if not isinstance(svc, dict):
                    continue

                # Parse endpoints
                endpoints = []
                for ep in svc.get("endpoints", []):
                    if isinstance(ep, dict):
                        endpoints.append(ServiceEndpoint(
                            path=ep.get("path", "/"),
                            methods=ep.get("methods", ["GET"]),
                        ))

                # Parse inter-service calls
                calls = []
                for call in svc.get("inter_service_calls", []):
                    if isinstance(call, dict):
                        calls.append(InterServiceCall(
                            calls=call.get("calls", ""),
                            pattern=call.get("pattern", "sync_rest"),
                            frequency=call.get("frequency", "medium"),
                        ))

                proposed_services.append(ServiceBoundary(
                    name=svc.get("name", "unnamed-service"),
                    bounded_context=svc.get("bounded_context", ""),
                    modules=svc.get("modules", []),
                    tables=svc.get("tables", []),
                    endpoints=endpoints,
                    inter_service_calls=calls,
                    external_dependencies=svc.get("external_dependencies", []),
                    confidence_score=min(max(svc.get("confidence_score", 0.8), 0.0), 1.0),
                    reason=svc.get("reason", ""),
                ))
        else:
            # Fallback: generate from communities
            proposed_services = self._services_from_communities(communities, analyzer_output)

        return ArchitectOutput(
            proposed_services=proposed_services,
            inter_service_patterns=llm_result.get("inter_service_patterns", {}),
            data_ownership=llm_result.get("data_ownership", {}),
        )

    def _services_from_communities(
        self,
        communities: Dict[str, int],
        analyzer_output: AnalyzerOutput,
    ) -> List[ServiceBoundary]:
        """Generate service proposals from Louvain communities as fallback."""
        # Group by community
        groups = {}
        for node_id, comm_id in communities.items():
            if comm_id not in groups:
                groups[comm_id] = []
            groups[comm_id].append(node_id)

        services = []
        for comm_id, node_ids in groups.items():
            # Get the modules in this community
            modules = list(set(
                nid.split(".")[0] for nid in node_ids if "." in nid
            ))

            if not modules:
                continue

            service_name = "-".join(modules[:2]) + "-service"

            services.append(ServiceBoundary(
                name=service_name,
                bounded_context=f"Domain covering: {', '.join(modules)}",
                modules=modules,
                tables=[],
                endpoints=[ServiceEndpoint(path=f"/api/{modules[0]}", methods=["GET", "POST"])],
                confidence_score=0.7,
                reason=f"Community detection grouped {len(node_ids)} nodes",
            ))

        return services
