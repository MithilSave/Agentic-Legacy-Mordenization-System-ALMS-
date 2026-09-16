"""
Agents — Test-Gen Agent
==========================
Test suite generation with shadow testing for functional parity.

Per IMPLEMENTATION_PLAN_v2.md §5:
- pytest + hypothesis property tests
- Shadow testing: legacy vs. generated, exact-match comparison
- Sampled subset (~15-20 representative cases)
- Second HITL checkpoint here

Extension — py_compile gate:
- Each generated test case is validated with py_compile individually
- If any test fails validation, the LLM is re-called with the error as
  feedback, up to ``config.max_retries`` attempts
- Only test cases that pass py_compile are included in the final output
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple

import ollama as ollama_client

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

    **py_compile gate**: every generated test case is validated with
    ``py_compile`` before being accepted.  Invalid tests trigger a
    retry loop (with the compile error fed back to the LLM) up to
    ``config.max_retries`` attempts.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        retriever: Optional[AgentRetriever] = None,
    ):
        self.config = config or Config()
        self.retriever = retriever
        self.agent_config = self.config.get_agent_config("test_gen")

    def generate_tests(
        self,
        refactoring_output: RefactoringOutput,
        legacy_code: Dict[str, str],
    ) -> TestGenOutput:
        """Generate test suite for a refactored service.

        Implements a compile-validate-retry loop:
        1. Call LLM to generate tests
        2. Parse into individual TestCase objects
        3. Validate each with py_compile
        4. If any fail, retry with error feedback (up to max_retries)
        5. Only emit valid tests

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

        # ── Step 3: Compile-validate-retry loop ──
        max_attempts = self.config.max_retries
        all_valid: List[TestCase] = []
        all_errors: List[str] = []
        raw_tests = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Test generation attempt {attempt}/{max_attempts} for {service_name}")

            # Call LLM (first attempt uses normal prompt; retries include error feedback)
            if attempt == 1:
                raw_tests = self._call_llm(
                    service_name, generated_code, legacy_combined, rag_context
                )
            else:
                raw_tests = self._retry_with_feedback(
                    service_name, generated_code, legacy_combined,
                    rag_context, raw_tests, all_errors
                )

            # Parse into individual test cases
            test_cases = self._parse_tests(raw_tests, service_name)

            if not test_cases:
                all_errors.append(f"Attempt {attempt}: LLM returned no parseable test cases")
                logger.warning(f"Attempt {attempt}: No test cases parsed")
                continue

            # Validate each test case individually
            valid, errors = self._compile_validate_tests(test_cases)
            all_valid = valid
            all_errors = errors

            if not errors:
                logger.info(
                    f"Attempt {attempt}: All {len(valid)} tests passed py_compile ✓"
                )
                break

            logger.warning(
                f"Attempt {attempt}: {len(errors)} of {len(test_cases)} tests "
                f"failed py_compile, {len(valid)} valid"
            )

            if attempt == max_attempts:
                logger.warning(
                    f"Max retries reached for {service_name} — "
                    f"emitting {len(valid)} valid tests, discarding {len(errors)} invalid"
                )

        # ── Step 4: Create shadow test stubs ──
        shadow_results = self._create_shadow_stubs(service_name)

        py_compile_passed = len(all_errors) == 0 and len(all_valid) > 0

        output = TestGenOutput(
            service_name=service_name,
            test_cases=all_valid,
            shadow_results=shadow_results,
            coverage_target=85.0,
            total_tests=len(all_valid),
            passed_tests=0,  # Not executed yet
            py_compile_passed=py_compile_passed,
            compile_errors=all_errors,
        )

        status = "PASS" if py_compile_passed else "PARTIAL"
        logger.info(
            f"═══ TEST-GEN AGENT: Complete — {len(all_valid)} valid tests, "
            f"py_compile={status} ═══"
        )
        return output

    # ──────────────────────────────────────────────
    #  py_compile Validation
    # ──────────────────────────────────────────────

    def _compile_validate_tests(
        self, test_cases: List[TestCase]
    ) -> Tuple[List[TestCase], List[str]]:
        """Validate each test case individually with py_compile.

        Returns:
            (valid_tests, error_messages) — only valid tests are kept
        """
        valid: List[TestCase] = []
        errors: List[str] = []

        for tc in test_cases:
            if not tc.code.strip():
                errors.append(f"Test '{tc.name}' has empty code body")
                continue

            if validate_syntax(tc.code):
                valid.append(tc)
            else:
                errors.append(f"Test '{tc.name}' failed py_compile validation")
                logger.warning(f"py_compile FAIL: {tc.name}")

        return valid, errors

    def _retry_with_feedback(
        self,
        service_name: str,
        generated_code: str,
        legacy_code: str,
        rag_context: str,
        previous_output: str,
        errors: List[str],
    ) -> str:
        """Re-call the LLM with compile error feedback for self-correction.

        Includes the previous (broken) output and the specific py_compile
        errors so the LLM can fix them.
        """
        error_summary = "\n".join(f"  - {e}" for e in errors)

        prompt = TESTGEN_SYSTEM_PROMPT.format(
            rag_testing_patterns=rag_context or "No testing patterns retrieved.",
            generated_service_code=generated_code[:4000],
            legacy_service_code=legacy_code[:2000],
        )

        try:
            response = ollama_client.chat(
                model=self.config.ollama_model,
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
                    {"role": "assistant", "content": previous_output},
                    {"role": "user", "content": (
                        "The previous test code FAILED py_compile syntax validation. "
                        "The following errors were detected:\n"
                        f"{error_summary}\n\n"
                        "Please fix all syntax errors and regenerate the COMPLETE "
                        "test suite. Make sure every test function is valid Python "
                        "that passes py_compile. Common issues:\n"
                        "- Unterminated strings or f-strings\n"
                        "- Missing imports\n"
                        "- Incorrect indentation\n"
                        "- Unbalanced parentheses/brackets\n"
                        "Return the corrected, complete Python test code."
                    )},
                ],
                options={
                    "num_ctx": self.agent_config["num_ctx"],
                    "temperature": self.agent_config["temperature"],
                },
            )

            return response.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"LLM retry call failed: {e}")
            return ""

    # ──────────────────────────────────────────────
    #  LLM Interaction
    # ──────────────────────────────────────────────

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
            response = ollama_client.chat(
                model=self.config.ollama_model,
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

            return response.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    # ──────────────────────────────────────────────
    #  Parsing & Classification
    # ──────────────────────────────────────────────

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

        # Validate full-block syntax first for fast-path
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
            # If full-block syntax is invalid, save the whole thing as one test
            # block — the compile-validate step will catch and report it
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
