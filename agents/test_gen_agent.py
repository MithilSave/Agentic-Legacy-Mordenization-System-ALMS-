"""
Agents — Test-Gen Agent
==========================
Test suite generation with shadow testing for functional parity.

Per IMPLEMENTATION_PLAN_v2.md §5:
- pytest + hypothesis property tests
- Shadow testing: legacy vs. generated, exact-match comparison
- Sampled subset (~15-20 representative cases)
- Second HITL checkpoint here
"""

import json
import logging
from typing import Dict, Any, Optional, List

from ollama import Client as OllamaClient

from core.config import Config
from core.constants import (
    TestGenOutput, TestCase, ShadowTestResult,
    RefactoringOutput, TESTGEN_SYSTEM_PROMPT
)
from tools.code_generation import validate_syntax
from rag.retriever import AgentRetriever

logger = logging.getLogger("agents.test_gen")


class TestGenAgent:
    """Test Generation Agent.

    Generates pytest test suites for refactored FastAPI services.
    Includes unit tests, integration tests, shadow tests, and
    property-based tests using hypothesis.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        retriever: Optional[AgentRetriever] = None,
    ):
        self.config = config or Config()
        self.retriever = retriever
        self.agent_config = self.config.get_agent_config("test_gen")
        self.ollama = OllamaClient(host=self.config.ollama_host, timeout=1800.0)

    def generate_tests(
        self,
        refactoring_output: RefactoringOutput,
        legacy_code: Dict[str, str],
    ) -> TestGenOutput:
        """Generate test suite for a refactored service.

        Args:
            refactoring_output: Output from the Refactoring Agent
            legacy_code: Dict of filename -> legacy source code

        Returns:
            TestGenOutput with test cases and shadow test stubs
        """
        service_name = refactoring_output.service_name
        logger.info(f"═══ TEST-GEN AGENT: Generating tests for {service_name} ═══")

        # ── Step 1: Collect generated code ──
        generated_code = "\n\n".join(f.content for f in refactoring_output.files)
        legacy_combined = "\n\n".join(
            f"# {fname}\n{code}" for fname, code in legacy_code.items()
        )

        # ── Step 2: RAG retrieval ──
        rag_context = ""
        if self.retriever:
            logger.info("Retrieving testing patterns...")
            rag_context = self.retriever.retrieve_for_test_gen(
                f"Generate tests for {service_name} FastAPI service"
            )

        # ── Step 3: Call LLM ──
        logger.info("Calling LLM for test generation...")
        raw_tests = self._call_llm(service_name, generated_code, legacy_combined, rag_context)

        # ── Step 4: Parse and validate tests ──
        test_cases = self._parse_tests(raw_tests, service_name)

        # ── Step 5: Create shadow test stubs ──
        shadow_results = self._create_shadow_stubs(service_name)

        output = TestGenOutput(
            service_name=service_name,
            test_cases=test_cases,
            shadow_results=shadow_results,
            coverage_target=85.0,
            total_tests=len(test_cases),
            passed_tests=0,  # Not executed yet
        )

        logger.info(f"═══ TEST-GEN AGENT: Complete — {len(test_cases)} tests generated ═══")
        return output

    def _call_llm(
        self,
        service_name: str,
        generated_code: str,
        legacy_code: str,
        rag_context: str,
    ) -> str:
        """Call Ollama for test generation."""
        prompt = TESTGEN_SYSTEM_PROMPT.format(
            rag_testing_patterns=rag_context or "No testing patterns retrieved.",
            generated_service_code=generated_code[:4000],
            legacy_service_code=legacy_code[:2000],
        )

        try:
            response = self.ollama.chat(
                model=self.agent_config["model"],
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": (
                        f"Generate a comprehensive pytest test suite for the '{service_name}' "
                        "FastAPI service. Include: "
                        "1) Unit tests for each endpoint (happy + error paths), "
                        "2) At least one property-based test using hypothesis, "
                        "3) Shadow test comparing legacy vs new output. "
                        "Return complete Python test code."
                    )},
                ],
                options={
                    "num_ctx": self.agent_config["num_ctx"],
                    "temperature": self.agent_config["temperature"],
                },
            )

            # ── Token Usage Logging ──
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens
            total_duration_ms = response.get("total_duration", 0) / 1e6  # ns → ms
            eval_duration_ms = response.get("eval_duration", 0) / 1e6
            tokens_per_sec = (completion_tokens / (eval_duration_ms / 1000.0)) if eval_duration_ms > 0 else 0
            logger.info(
                f"[TOKENS] TestGen LLM call — "
                f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, "
                f"Total: {total_tokens} | "
                f"Speed: {tokens_per_sec:.1f} tok/s | "
                f"Duration: {total_duration_ms:.0f}ms"
            )

            return response.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_tests(self, raw_tests: str, service_name: str) -> List[TestCase]:
        """Parse LLM output into structured test cases."""
        test_cases = []

        if not raw_tests:
            logger.warning("No tests generated by LLM")
            return test_cases

        # Clean up markdown formatting
        clean_code = raw_tests
        if "```python" in clean_code:
            parts = clean_code.split("```python")
            if len(parts) > 1:
                clean_code = parts[1].split("```")[0]
        elif "```" in clean_code:
            parts = clean_code.split("```")
            if len(parts) > 1:
                clean_code = parts[1]

        # Validate syntax
        if validate_syntax(clean_code):
            # Split into individual test functions
            lines = clean_code.split("\n")
            current_test = None
            current_lines = []
            import_lines = []
            in_imports = True

            for line in lines:
                if line.startswith("def test_") or line.startswith("async def test_"):
                    if current_test and current_lines:
                        test_code = "\n".join(import_lines + [""] + current_lines)
                        test_cases.append(TestCase(
                            name=current_test,
                            test_type=self._infer_test_type(current_test),
                            code=test_code,
                        ))

                    current_test = line.split("(")[0].replace("def ", "").replace("async def ", "").strip()
                    current_lines = [line]
                    in_imports = False
                elif current_test:
                    current_lines.append(line)
                elif in_imports and (line.startswith("import ") or line.startswith("from ") or
                                      line.startswith("@") or line.strip() == "" or
                                      line.startswith("#")):
                    import_lines.append(line)

            # Save last test
            if current_test and current_lines:
                test_code = "\n".join(import_lines + [""] + current_lines)
                test_cases.append(TestCase(
                    name=current_test,
                    test_type=self._infer_test_type(current_test),
                    code=test_code,
                ))
        else:
            # If syntax is invalid, save the whole thing as one test block
            test_cases.append(TestCase(
                name=f"test_{service_name.replace('-', '_')}_suite",
                test_type="unit",
                code=clean_code,
            ))

        return test_cases

    def _infer_test_type(self, test_name: str) -> str:
        """Infer test type from the test function name."""
        name_lower = test_name.lower()
        if "shadow" in name_lower or "parity" in name_lower:
            return "shadow"
        elif "integration" in name_lower or "e2e" in name_lower:
            return "integration"
        elif "property" in name_lower or "hypothesis" in name_lower:
            return "property"
        return "unit"

    def _create_shadow_stubs(self, service_name: str) -> List[ShadowTestResult]:
        """Create shadow test result stubs (actual comparison happens at runtime)."""
        return [
            ShadowTestResult(
                test_name=f"shadow_{service_name}_health_check",
                passed=False,
                legacy_output=None,
                new_output=None,
            ),
            ShadowTestResult(
                test_name=f"shadow_{service_name}_crud_parity",
                passed=False,
                legacy_output=None,
                new_output=None,
            ),
        ]
