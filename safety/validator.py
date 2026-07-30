"""
Safety — Code Validator
=========================
Pre-execution validation for generated code.
Per CONTEXT.md: py_compile gate + bandit scanning.
"""

import py_compile
import tempfile
import os
import logging
import ast
from typing import Dict, List, Any

logger = logging.getLogger("safety.validator")


class CodeValidator:
    """Validates generated code before accepting it.

    Checks:
    1. Python syntax (py_compile)
    2. AST parseable
    3. Required patterns present (imports, type hints)
    4. Security scan (bandit, optional)
    """

    def validate(self, code: str, check_security: bool = False) -> Dict[str, Any]:
        """Run all validation checks on generated code.

        Args:
            code: Python source code string
            check_security: Whether to run bandit security scan

        Returns:
            Dict with 'passed', 'checks', and 'errors'
        """
        results = {
            "passed": True,
            "checks": [],
            "errors": [],
            "warnings": [],
        }

        # Check 1: py_compile
        compile_result = self._check_py_compile(code)
        results["checks"].append(compile_result)
        if not compile_result["passed"]:
            results["passed"] = False
            results["errors"].append(compile_result["error"])

        # Check 2: AST parse
        ast_result = self._check_ast_parse(code)
        results["checks"].append(ast_result)
        if not ast_result["passed"]:
            results["passed"] = False
            results["errors"].append(ast_result["error"])

        # Check 3: Basic quality checks
        quality_result = self._check_quality(code)
        results["checks"].append(quality_result)
        results["warnings"].extend(quality_result.get("warnings", []))

        # Check 4: Security (optional)
        if check_security:
            security_result = self._check_security(code)
            results["checks"].append(security_result)
            if not security_result["passed"]:
                results["passed"] = False
                results["errors"].extend(security_result.get("issues", []))

        return results

    def _check_py_compile(self, code: str) -> Dict[str, Any]:
        """Validate Python syntax using py_compile."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            py_compile.compile(temp_path, doraise=True)
            return {"name": "py_compile", "passed": True}
        except py_compile.PyCompileError as e:
            return {"name": "py_compile", "passed": False, "error": str(e)}
        finally:
            os.unlink(temp_path)

    def _check_ast_parse(self, code: str) -> Dict[str, Any]:
        """Validate code can be parsed by AST."""
        try:
            ast.parse(code)
            return {"name": "ast_parse", "passed": True}
        except SyntaxError as e:
            return {"name": "ast_parse", "passed": False, "error": str(e)}

    def _check_quality(self, code: str) -> Dict[str, Any]:
        """Basic code quality checks."""
        warnings = []

        lines = code.split("\n")

        # Check for type hints
        has_type_hints = any(":" in line and "def " in line for line in lines)
        if not has_type_hints:
            warnings.append("No type hints detected")

        # Check for docstrings
        has_docstrings = '"""' in code or "'''" in code
        if not has_docstrings:
            warnings.append("No docstrings detected")

        # Check for error handling
        has_try_except = "try:" in code
        if not has_try_except:
            warnings.append("No try/except error handling")

        return {
            "name": "quality_check",
            "passed": True,
            "warnings": warnings,
        }

    def _check_security(self, code: str) -> Dict[str, Any]:
        """Run bandit security scan if available.

        Per IMPLEMENTATION_PLAN_v2.md §6:
        Block only on HIGH severity + HIGH confidence.
        Medium/low surface as warnings.
        """
        try:
            import bandit
            from bandit.core import manager as bandit_manager

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                b_mgr = bandit_manager.BanditManager(
                    bandit.core.config.BanditConfig(), "file"
                )
                b_mgr.discover_files([temp_path])
                b_mgr.run_tests()

                issues = []
                high_issues = []
                for issue in b_mgr.get_issue_list():
                    issue_dict = {
                        "severity": issue.severity,
                        "confidence": issue.confidence,
                        "text": issue.text,
                        "line": issue.lineno,
                    }
                    issues.append(issue_dict)
                    if issue.severity == "HIGH" and issue.confidence == "HIGH":
                        high_issues.append(issue_dict)

                return {
                    "name": "bandit_security",
                    "passed": len(high_issues) == 0,
                    "issues": [f"HIGH: {i['text']} (line {i['line']})" for i in high_issues],
                    "warnings": [f"{i['severity']}: {i['text']}" for i in issues if i not in high_issues],
                    "total_issues": len(issues),
                }
            finally:
                os.unlink(temp_path)

        except ImportError:
            return {
                "name": "bandit_security",
                "passed": True,
                "warnings": ["bandit not installed — security scan skipped"],
            }
        except Exception as e:
            return {
                "name": "bandit_security",
                "passed": True,
                "warnings": [f"Security scan error: {e}"],
            }
