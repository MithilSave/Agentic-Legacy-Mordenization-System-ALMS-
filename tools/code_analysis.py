"""
Tools — Code Analysis
======================
AST-based code structure extraction per CONTEXT.md §9.
Extracts functions, classes, imports, and global variables.
Uses radon for cyclomatic complexity and NetworkX for dependency graphs.

IMPORTANT: The AST pre-filter applies ONLY to the Analyzer agent.
Per CONTEXT.md §15: applying it everywhere strips function bodies
from Refactoring/Test-Gen context.
"""

import ast
import os
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import networkx as nx

logger = logging.getLogger("tools.code_analysis")


# ══════════════════════════════════════════════
#  AST CODE STRUCTURE EXTRACTION
# ══════════════════════════════════════════════

def extract_code_structure(source_path: str) -> Dict[str, Any]:
    """Extract the complete code structure from a Python codebase.

    This is the primary analysis function per CONTEXT.md §9:
    - AST-only extraction
    - Functions, classes, imports, global variables
    - No full function bodies (those are for Refactoring/Test-Gen)

    Args:
        source_path: Path to the codebase directory or single file

    Returns:
        Dict with modules, functions, classes, imports, globals, and metrics
    """
    source_path = Path(source_path)

    if source_path.is_file():
        files = [source_path]
    elif source_path.is_dir():
        files = list(source_path.rglob("*.py"))
    else:
        raise ValueError(f"Invalid source path: {source_path}")

    structure = {
        "modules": [],
        "functions": [],
        "classes": [],
        "imports": [],
        "global_variables": [],
        "file_contents": {},
        "stats": {
            "total_files": 0,
            "total_lines": 0,
            "total_functions": 0,
            "total_classes": 0,
        }
    }

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            module_name = file_path.stem
            rel_path = str(file_path.relative_to(source_path.parent if source_path.is_file() else source_path))

            structure["file_contents"][rel_path] = content

            module_info = _analyze_module(content, module_name, rel_path)
            structure["modules"].append(module_info)
            structure["functions"].extend(module_info["functions"])
            structure["classes"].extend(module_info["classes"])
            structure["imports"].extend(module_info["imports"])
            structure["global_variables"].extend(module_info["globals"])

            lines = content.count("\n") + 1
            structure["stats"]["total_files"] += 1
            structure["stats"]["total_lines"] += lines
            structure["stats"]["total_functions"] += len(module_info["functions"])
            structure["stats"]["total_classes"] += len(module_info["classes"])

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            continue

    return structure


def _analyze_module(source_code: str, module_name: str, file_path: str) -> Dict[str, Any]:
    """Analyze a single Python module via AST parsing."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return {
            "name": module_name,
            "file": file_path,
            "functions": [],
            "classes": [],
            "imports": [],
            "globals": [],
            "errors": [str(e)],
        }

    functions = []
    classes = []
    imports = []
    globals_list = []

    for node in ast.walk(tree):
        # ── Functions ──
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            func_info = _extract_function_info(node, module_name)
            functions.append(func_info)

        # ── Classes ──
        elif isinstance(node, ast.ClassDef):
            class_info = _extract_class_info(node, module_name)
            classes.append(class_info)

        # ── Imports ──
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": module_name,
                    "imported": alias.name,
                    "alias": alias.asname,
                    "type": "import",
                })

        elif isinstance(node, ast.ImportFrom):
            import_module = node.module or ""
            for alias in node.names:
                imports.append({
                    "module": module_name,
                    "imported": f"{import_module}.{alias.name}",
                    "from_module": import_module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "type": "from_import",
                })

    # ── Global Variables (top-level assignments) ──
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    globals_list.append({
                        "module": module_name,
                        "name": target.id,
                        "line": node.lineno,
                    })

    return {
        "name": module_name,
        "file": file_path,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "globals": globals_list,
        "errors": [],
    }


def _extract_function_info(node, module_name: str) -> Dict[str, Any]:
    """Extract function metadata from an AST FunctionDef node."""
    # Get parameter names
    params = []
    for arg in node.args.args:
        params.append(arg.arg)

    # Get function calls within this function
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            call_name = _get_call_name(child)
            if call_name:
                calls.append(call_name)

    # Calculate basic complexity (number of branches)
    complexity = _calculate_complexity(node)

    # Lines of code
    loc = (node.end_lineno or node.lineno) - node.lineno + 1

    # Docstring
    docstring = ast.get_docstring(node)

    return {
        "id": f"{module_name}.{node.name}",
        "name": node.name,
        "module": module_name,
        "type": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
        "parameters": params,
        "calls": calls,
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "loc": loc,
        "complexity": complexity,
        "docstring": docstring[:100] if docstring else None,
    }


def _extract_class_info(node, module_name: str) -> Dict[str, Any]:
    """Extract class metadata from an AST ClassDef node."""
    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(item.name)

    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(f"{_get_attribute_name(base)}")

    return {
        "id": f"{module_name}.{node.name}",
        "name": node.name,
        "module": module_name,
        "type": "class",
        "methods": methods,
        "bases": bases,
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "docstring": ast.get_docstring(node),
    }


def _get_call_name(node: ast.Call) -> Optional[str]:
    """Extract the name of a function call from an AST Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    elif isinstance(node.func, ast.Attribute):
        return _get_attribute_name(node.func)
    return None


def _get_attribute_name(node: ast.Attribute) -> str:
    """Recursively get dotted attribute name."""
    if isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    elif isinstance(node.value, ast.Attribute):
        return f"{_get_attribute_name(node.value)}.{node.attr}"
    return node.attr


def _calculate_complexity(node) -> int:
    """Calculate a basic cyclomatic complexity score for a function.

    Counts decision points: if, elif, for, while, except, and, or,
    with, assert, ternary expressions.
    """
    complexity = 1  # Base complexity

    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            complexity += 1
        elif isinstance(child, ast.For):
            complexity += 1
        elif isinstance(child, ast.While):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # Each 'and'/'or' adds a branch
            complexity += len(child.values) - 1
        elif isinstance(child, ast.Assert):
            complexity += 1

    return complexity


# ══════════════════════════════════════════════
#  DEPENDENCY GRAPH CONSTRUCTION
# ══════════════════════════════════════════════

def build_dependency_graph(code_structure: Dict[str, Any]) -> nx.DiGraph:
    """Build a NetworkX directed graph from analyzed code structure.

    Nodes = functions, classes, modules
    Edges = calls, imports, inheritance
    """
    G = nx.DiGraph()

    # Known external (3rd-party) top-level module names, so genuine library
    # coupling is kept while builtins / stdlib-method / local-variable calls
    # are NOT added as graph nodes (they are not architectural dependencies).
    known_external = set(get_external_dependencies(code_structure))
    known_class_names = {c["name"] for c in code_structure["classes"]}
    known_class_names |= {c["id"] for c in code_structure["classes"]}

    # Add module nodes
    for module in code_structure["modules"]:
        G.add_node(module["name"], type="module", file=module["file"])

    # Add function nodes and call edges
    for func in code_structure["functions"]:
        G.add_node(func["id"], type=func["type"], module=func["module"],
                   complexity=func["complexity"], loc=func["loc"],
                   parameters=len(func["parameters"]))

        # Add edges for function calls
        for call in func.get("calls", []):
            # Try to resolve the call to a known function
            target = _resolve_call(call, func["module"], code_structure)
            if target:
                G.add_edge(func["id"], target, type="internal_call", confidence=0.9)
            elif call.split(".")[0] in known_external:
                # Genuine 3rd-party library call — keep the coupling signal
                G.add_edge(func["id"], call.split(".")[0], type="external_call", confidence=0.7)
            # else: builtin / stdlib method / local-variable method / unknown
            #       — dropped so it does not pollute coupling & communities

    # Add class nodes
    for cls in code_structure["classes"]:
        G.add_node(cls["id"], type="class", module=cls["module"],
                   methods=cls["methods"])

        # Inheritance edges — only to entities we actually know about
        for base in cls.get("bases", []):
            base_head = base.split(".")[0]
            if base in known_class_names or base.split(".")[-1] in known_class_names:
                G.add_edge(cls["id"], base, type="inheritance", confidence=0.95)
            elif base_head in known_external:
                G.add_edge(cls["id"], base_head, type="inheritance", confidence=0.95)

    # Add import edges (module-level dependencies)
    for imp in code_structure["imports"]:
        if imp["type"] == "from_import":
            from_mod = imp.get("from_module", "")
            # Check if this is an internal module
            known_modules = {m["name"] for m in code_structure["modules"]}
            if from_mod in known_modules:
                G.add_edge(imp["module"], from_mod, type="import", confidence=1.0)

    return G


def _resolve_call(call_name: str, current_module: str, structure: Dict) -> Optional[str]:
    """Try to resolve a function call to a known function in the codebase."""
    # Direct name match in same module
    for func in structure["functions"]:
        if func["name"] == call_name and func["module"] == current_module:
            return func["id"]

    # Cross-module match (dotted name)
    for func in structure["functions"]:
        if func["id"] == call_name or func["name"] == call_name:
            return func["id"]

    return None


def find_circular_dependencies(G: nx.DiGraph) -> List[List[str]]:
    """Find all circular dependencies in the graph."""
    try:
        cycles = list(nx.simple_cycles(G))
        # Filter to meaningful cycles (not self-loops)
        return [c for c in cycles if len(c) > 1]
    except Exception:
        return []


def find_coupling_hotspots(G: nx.DiGraph, threshold: int = 3) -> List[Dict[str, Any]]:
    """Find modules with high coupling (many cross-module edges).

    Args:
        G: The dependency graph
        threshold: Minimum number of cross-module connections to flag

    Returns:
        List of hotspot dicts with module, coupled_to, and severity
    """
    # Group nodes by module
    module_edges = {}

    for u, v, data in G.edges(data=True):
        u_module = G.nodes[u].get("module", u.split(".")[0] if "." in u else u)
        v_module = G.nodes[v].get("module", v.split(".")[0] if "." in v else v)

        if u_module != v_module:
            if u_module not in module_edges:
                module_edges[u_module] = set()
            module_edges[u_module].add(v_module)

    hotspots = []
    for module, coupled_modules in module_edges.items():
        if len(coupled_modules) >= threshold:
            severity = "HIGH" if len(coupled_modules) >= 5 else "MEDIUM" if len(coupled_modules) >= 3 else "LOW"
            hotspots.append({
                "module": module,
                "coupled_to": list(coupled_modules),
                "severity": severity,
                "reason": f"{module} depends on {len(coupled_modules)} other modules: {', '.join(coupled_modules)}",
            })

    return sorted(hotspots, key=lambda h: len(h["coupled_to"]), reverse=True)


# ══════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════

def compute_codebase_hash(source_path: str) -> str:
    """Compute SHA-256 hash of the entire codebase for caching.

    Per CONTEXT.md §11: cache keyed on codebase hash.
    """
    source_path = Path(source_path)
    hasher = hashlib.sha256()

    if source_path.is_file():
        files = [source_path]
    else:
        files = sorted(source_path.rglob("*.py"))

    for f in files:
        try:
            content = f.read_bytes()
            hasher.update(content)
        except Exception:
            continue

    return hasher.hexdigest()


def graph_to_dict(G: nx.DiGraph) -> Dict[str, Any]:
    """Convert a NetworkX graph to a serializable dict."""
    nodes = []
    for node_id, data in G.nodes(data=True):
        nodes.append({"id": node_id, **data})

    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({"source": u, "target": v, **data})

    return {"nodes": nodes, "edges": edges}


def get_external_dependencies(code_structure: Dict[str, Any]) -> List[str]:
    """Extract external (non-local) library dependencies."""
    known_modules = {m["name"] for m in code_structure["modules"]}
    stdlib_modules = {
        "os", "sys", "json", "logging", "datetime", "hashlib", "secrets",
        "uuid", "random", "pathlib", "typing", "enum", "ast", "re",
        "collections", "functools", "itertools", "abc", "copy", "math",
        "sqlite3", "io", "time", "threading", "dataclasses", "contextlib",
    }

    external = set()
    for imp in code_structure["imports"]:
        mod = imp.get("from_module", imp.get("imported", "")).split(".")[0]
        if mod and mod not in known_modules and mod not in stdlib_modules:
            external.add(mod)

    return sorted(external)
