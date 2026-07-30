"""
RAG — Agent-Specific Retriever
================================
Scoped retrieval with category filters for each agent.
Per IMPLEMENTATION_PLAN_v2.md:
- Analyzer: refactoring_patterns only, top_k=3
- Architect: ddd_patterns only, top_k=3
- Refactoring: fastapi_patterns + security_patterns, top_k=3
- Test-Gen: testing_patterns, top_k=3
"""

import logging
from typing import List, Dict, Any, Optional

from core.config import Config
from rag.vector_store import VectorStore

logger = logging.getLogger("rag.retriever")


class AgentRetriever:
    """Context-aware retrieval tailored to each agent.

    Each agent gets retrieval scoped to specific KB categories
    with configurable top_k, per config.yaml.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.vector_store = vector_store or VectorStore(self.config)

    def retrieve_for_agent(
        self,
        agent_name: str,
        query: str,
        additional_context: str = "",
    ) -> str:
        """Retrieve RAG context for a specific agent.

        Args:
            agent_name: One of 'analyzer', 'architect', 'refactoring', 'test_gen'
            query: The retrieval query
            additional_context: Extra context to append to query

        Returns:
            Formatted string of retrieved documents for prompt injection
        """
        agent_cfg = self.config.get_agent_config(agent_name)
        categories = agent_cfg.get("rag_categories", [])
        top_k = agent_cfg.get("rag_top_k", 3)

        if not categories:
            logger.warning(f"No RAG categories configured for agent: {agent_name}")
            return ""

        full_query = f"{query} {additional_context}".strip()

        # Retrieve from each category and merge
        all_results = []
        for category in categories:
            results = self.vector_store.query(
                query_text=full_query,
                top_k=top_k,
                category_filter=category,
            )
            all_results.extend(results)

        if not all_results:
            logger.info(f"No RAG results for {agent_name}: '{full_query[:50]}...'")
            return "No relevant patterns found in the knowledge base."

        # Sort by score and take top_k overall
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = all_results[:top_k]

        # Format for prompt injection
        return self._format_results(top_results, agent_name)

    def retrieve_for_analyzer(self, codebase_description: str) -> str:
        """Retrieve refactoring patterns for the Analyzer Agent."""
        return self.retrieve_for_agent(
            "analyzer",
            "Common monolithic code patterns, dependency antipatterns, coupling hotspots",
            codebase_description,
        )

    def retrieve_for_architect(self, dependency_summary: str) -> str:
        """Retrieve DDD patterns for the Architect Agent."""
        return self.retrieve_for_agent(
            "architect",
            "Domain-Driven Design bounded context patterns, microservice boundaries",
            dependency_summary,
        )

    def retrieve_for_refactoring(self, legacy_code_description: str) -> str:
        """Retrieve FastAPI + security patterns for the Refactoring Agent."""
        return self.retrieve_for_agent(
            "refactoring",
            "FastAPI patterns, code transformation, security best practices",
            legacy_code_description,
        )

    def retrieve_for_test_gen(self, service_description: str) -> str:
        """Retrieve testing patterns for the Test-Gen Agent."""
        return self.retrieve_for_agent(
            "test_gen",
            "pytest patterns, shadow testing, property-based testing",
            service_description,
        )

    def _format_results(self, results: List[Dict], agent_name: str) -> str:
        """Format retrieved documents for prompt injection."""
        lines = []
        for i, result in enumerate(results, 1):
            category = result["metadata"].get("category", "unknown")
            document = result["metadata"].get("document", "unknown")
            score = result["score"]

            lines.append(f"--- Reference {i} [{category}/{document}] (relevance: {score:.2f}) ---")
            lines.append(result["content"])
            lines.append("")

        return "\n".join(lines)
