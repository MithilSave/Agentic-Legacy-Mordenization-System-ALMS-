"""
Agents — Refactoring Agent
=============================
FastAPI code generation from legacy monolithic code.

Per IMPLEMENTATION_PLAN_v2.md §4:
- num_ctx: 6144 — only agent needing this; needs full function bodies
- AST pre-filter MUST NOT apply here — needs full function bodies
- Jinja2 templates + py_compile gate before Test-Gen handoff
- RAG scoped to fastapi_patterns + security_patterns
"""

import json
import logging
from typing import Dict, Any, Optional, List

import ollama as ollama_client

from core.config import Config
from core.constants import (
    RefactoringOutput, GeneratedFile, ArchitectOutput,
    ServiceBoundary, REFACTORING_SYSTEM_PROMPT
)
from tools.code_generation import format_code, validate_syntax
from rag.retriever import AgentRetriever

logger = logging.getLogger("agents.refactoring")


class RefactoringAgent:
    """Refactoring Agent — FastAPI microservice code generation.

    IMPORTANT: This agent receives FULL function bodies, not AST summaries.
    The AST pre-filter is NOT applied here (CONTEXT.md §15 pitfall #3).
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        retriever: Optional[AgentRetriever] = None,
    ):
        self.config = config or Config()
        self.retriever = retriever
        self.agent_config = self.config.get_agent_config("refactoring")

    def refactor_service(
        self,
        service: ServiceBoundary,
        source_code: Dict[str, str],
    ) -> RefactoringOutput:
        """Generate a FastAPI microservice from legacy code.

        Args:
            service: Service boundary from the Architect Agent
            source_code: Dict of filename -> full source code content

        Returns:
            RefactoringOutput with generated files
        """
        logger.info(f"═══ REFACTORING AGENT: Generating {service.name} ═══")

        # ── Step 1: Extract relevant legacy code ──
        # FULL function bodies — no AST pre-filter!
        legacy_code = self._extract_relevant_code(service, source_code)

        # ── Step 2: RAG retrieval ──
        rag_fastapi = ""
        rag_security = ""
        if self.retriever:
            logger.info("Retrieving FastAPI and security patterns...")
            rag_fastapi = self.retriever.retrieve_for_refactoring(
                f"Convert {', '.join(service.modules)} to FastAPI service"
            )

        # ── Step 3: Call LLM for code generation ──
        logger.info("Calling LLM for code generation...")
        generated_code = self._call_llm(service, legacy_code, rag_fastapi, rag_security)

        # ── Step 4: Post-process ──
        logger.info("Post-processing generated code...")
        files = self._process_generated_code(service.name, generated_code)

        # ── Step 5: Validate ──
        py_compile_passed = True
        black_formatted = True
        for file in files:
            if file.file_type == "python":
                # Format with black/isort
                file.content = format_code(file.content)
                # py_compile gate
                if not validate_syntax(file.content):
                    py_compile_passed = False
                    logger.warning(f"py_compile failed for {file.filename}")

        output = RefactoringOutput(
            service_name=service.name,
            files=files,
            py_compile_passed=py_compile_passed,
            black_formatted=black_formatted,
            isort_applied=True,
        )

        logger.info(f"═══ REFACTORING AGENT: Complete — {len(files)} files generated, "
                     f"py_compile={'PASS' if py_compile_passed else 'FAIL'} ═══")
        return output

    def _extract_relevant_code(
        self, service: ServiceBoundary, source_code: Dict[str, str]
    ) -> str:
        """Extract the full source code relevant to this service.

        IMPORTANT: Returns FULL function bodies, not AST summaries.
        """
        relevant_parts = []

        for filename, content in source_code.items():
            # Check if this file's module is in the service's modules
            module_name = filename.replace(".py", "").split("/")[-1].split("\\")[-1]
            if module_name in service.modules:
                relevant_parts.append(f"# === {filename} ===\n{content}")

        if not relevant_parts:
            # If no direct match, include all code
            for filename, content in source_code.items():
                relevant_parts.append(f"# === {filename} ===\n{content}")

        return "\n\n".join(relevant_parts)

    def _call_llm(
        self,
        service: ServiceBoundary,
        legacy_code: str,
        rag_fastapi: str,
        rag_security: str,
    ) -> str:
        """Call Ollama for code generation."""
        service_def = {
            "name": service.name,
            "bounded_context": service.bounded_context,
            "modules": service.modules,
            "tables": service.tables,
            "endpoints": [ep.model_dump() for ep in service.endpoints],
        }

        prompt = REFACTORING_SYSTEM_PROMPT.format(
            rag_fastapi_patterns=rag_fastapi or "No patterns retrieved.",
            rag_security_patterns=rag_security or "No security patterns retrieved.",
            service_definition=json.dumps(service_def, indent=2),
            legacy_code=legacy_code[:6000],  # Stay within context window
        )

        try:
            response = ollama_client.chat(
                model=self.config.ollama_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": (
                        f"Generate a complete FastAPI microservice for '{service.name}'. "
                        "Include: main.py with app setup, models, schemas, endpoints, "
                        "database setup, and error handling. "
                        "Return the complete Python code."
                    )},
                ],
                options={
                    "num_ctx": self.agent_config["num_ctx"],  # 6144 — largest context
                    "temperature": self.agent_config["temperature"],
                },
            )

            return response.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _process_generated_code(self, service_name: str, raw_code: str) -> List[GeneratedFile]:
        """Process raw LLM output into structured files."""
        files = []

        if not raw_code:
            logger.warning("No code generated by LLM")
            return files

        # Try to extract code blocks from the response
        code_blocks = self._extract_code_blocks(raw_code)

        if code_blocks:
            for i, block in enumerate(code_blocks):
                filename = block.get("filename", f"{service_name.replace('-', '_')}_service.py")
                files.append(GeneratedFile(
                    filename=filename,
                    content=block["code"],
                    file_type="python",
                ))
        else:
            # Treat the entire response as a single Python file
            # Strip any markdown formatting
            clean_code = raw_code
            if "```python" in clean_code:
                parts = clean_code.split("```python")
                if len(parts) > 1:
                    clean_code = parts[1].split("```")[0]
            elif "```" in clean_code:
                parts = clean_code.split("```")
                if len(parts) > 1:
                    clean_code = parts[1]

            files.append(GeneratedFile(
                filename=f"{service_name.replace('-', '_')}_service.py",
                content=clean_code.strip(),
                file_type="python",
            ))

        return files

    def _extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """Extract named code blocks from LLM output."""
        blocks = []
        lines = text.split("\n")
        current_block = None
        current_code = []

        for line in lines:
            if line.strip().startswith("```python") or line.strip().startswith("```py"):
                if current_block is not None:
                    # Save previous block
                    blocks.append({
                        "filename": current_block,
                        "code": "\n".join(current_code),
                    })
                current_block = "generated.py"
                current_code = []
                # Check if filename is on the same line
                parts = line.strip().split()
                if len(parts) > 1:
                    potential_name = parts[-1]
                    if potential_name.endswith(".py"):
                        current_block = potential_name
            elif line.strip() == "```" and current_block is not None:
                blocks.append({
                    "filename": current_block,
                    "code": "\n".join(current_code),
                })
                current_block = None
                current_code = []
            elif current_block is not None:
                current_code.append(line)
            elif line.startswith("# ") and line.endswith(".py"):
                # Detect file markers like "# main.py"
                current_block = line.lstrip("# ").strip()

        return blocks
