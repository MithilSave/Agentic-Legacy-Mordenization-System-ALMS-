"""
Tools — Shadow Testing Engine
================================
Parallel execution for functional parity validation.
Compares legacy vs. generated system outputs.
"""

import logging
import json
import difflib
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger("tools.testing")


class ShadowTestingEngine:
    """Run identical inputs against legacy and new systems, compare outputs.

    Per IMPLEMENTATION_PLAN_v2.md §5:
    - Statistically sampled subset (~15-20 representative cases)
    - Exact-match comparison
    - Full endpoint testing doubles demo time for marginal gain
    """

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "discrepancies": [],
        }

    def run_shadow_tests(
        self,
        legacy_fn: Callable,
        new_fn: Callable,
        test_cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute identical inputs against both systems.

        Args:
            legacy_fn: Function to call on legacy system
            new_fn: Function to call on new system
            test_cases: List of test case dicts with 'name' and 'input'

        Returns:
            Results dict with pass/fail counts and discrepancies
        """
        self.results = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "discrepancies": [],
        }

        for test_case in test_cases:
            test_name = test_case.get("name", "unnamed")
            test_input = test_case.get("input", {})

            try:
                legacy_result = legacy_fn(**test_input)
                new_result = new_fn(**test_input)

                if self._compare_outputs(legacy_result, new_result):
                    self.results["passed"] += 1
                else:
                    self.results["failed"] += 1
                    diff = self._compute_diff(legacy_result, new_result)
                    self.results["discrepancies"].append({
                        "test": test_name,
                        "input": test_input,
                        "legacy_output": str(legacy_result),
                        "new_output": str(new_result),
                        "diff": diff,
                    })

            except Exception as e:
                self.results["errors"] += 1
                self.results["discrepancies"].append({
                    "test": test_name,
                    "input": test_input,
                    "error": str(e),
                })
                logger.error(f"Shadow test error for {test_name}: {e}")

        return self.results

    def _compare_outputs(self, legacy, new) -> bool:
        """Compare two outputs for functional equivalence."""
        if isinstance(legacy, dict) and isinstance(new, dict):
            return self._dict_equal(legacy, new)
        return str(legacy) == str(new)

    def _dict_equal(self, d1: dict, d2: dict) -> bool:
        """Deep compare two dicts, ignoring metadata fields."""
        ignore_keys = {"created_at", "updated_at", "timestamp", "id"}

        keys1 = set(d1.keys()) - ignore_keys
        keys2 = set(d2.keys()) - ignore_keys

        if keys1 != keys2:
            return False

        for key in keys1:
            v1, v2 = d1[key], d2[key]
            if isinstance(v1, dict) and isinstance(v2, dict):
                if not self._dict_equal(v1, v2):
                    return False
            elif isinstance(v1, list) and isinstance(v2, list):
                if len(v1) != len(v2):
                    return False
                for a, b in zip(v1, v2):
                    if isinstance(a, dict) and isinstance(b, dict):
                        if not self._dict_equal(a, b):
                            return False
                    elif str(a) != str(b):
                        return False
            elif str(v1) != str(v2):
                return False

        return True

    def _compute_diff(self, legacy, new) -> str:
        """Compute a unified diff between two outputs."""
        legacy_str = json.dumps(legacy, indent=2, default=str) if isinstance(legacy, dict) else str(legacy)
        new_str = json.dumps(new, indent=2, default=str) if isinstance(new, dict) else str(new)

        diff_lines = list(difflib.unified_diff(
            legacy_str.splitlines(),
            new_str.splitlines(),
            fromfile="legacy",
            tofile="new",
            lineterm=""
        ))

        return "\n".join(diff_lines)

    def generate_parity_report(self) -> str:
        """Generate a human-readable parity report."""
        r = self.results
        total = r["total_tests"]

        if total == 0:
            return "⚠ No tests executed."

        pass_rate = (r["passed"] / total) * 100

        lines = [
            "═" * 50,
            "  SHADOW TESTING PARITY REPORT",
            "═" * 50,
            f"  Total Tests:    {total}",
            f"  Passed:         {r['passed']}  ✓",
            f"  Failed:         {r['failed']}  ✗",
            f"  Errors:         {r['errors']}  ⚠",
            f"  Pass Rate:      {pass_rate:.1f}%",
            "─" * 50,
        ]

        if r["failed"] == 0 and r["errors"] == 0:
            lines.append("  ✅ 100% FUNCTIONAL PARITY ACHIEVED")
        else:
            lines.append(f"  ⚠️ {r['failed'] + r['errors']} DISCREPANCIES FOUND")
            lines.append("")
            for disc in r["discrepancies"][:5]:
                lines.append(f"  Test: {disc.get('test', 'unknown')}")
                if "error" in disc:
                    lines.append(f"    Error: {disc['error']}")
                elif "diff" in disc:
                    lines.append(f"    Diff:\n{disc['diff'][:200]}")
                lines.append("")

        lines.append("═" * 50)
        return "\n".join(lines)
