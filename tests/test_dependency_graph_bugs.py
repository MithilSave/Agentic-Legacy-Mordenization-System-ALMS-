"""Bug-reproduction tests for tools/code_analysis.py dependency graph.

These document defects found during a full-suite bug hunt. They are
expected to FAIL against the current implementation.
"""

from tools.code_analysis import (
    extract_code_structure,
    build_dependency_graph,
    find_coupling_hotspots,
)


def _structure_from_source(tmp_path, **modules):
    for name, src in modules.items():
        (tmp_path / f"{name}.py").write_text(src, encoding="utf-8")
    return extract_code_structure(str(tmp_path))


def test_builtin_calls_are_not_treated_as_module_coupling(tmp_path):
    """A function that only calls builtins/stdlib must not appear coupled
    to `str`, `len`, `ValueError`, `logger`, etc."""
    struct = _structure_from_source(
        tmp_path,
        alpha='''
import logging
logger = logging.getLogger(__name__)

def handle(value):
    logger.info("start")
    if not isinstance(value, str):
        raise ValueError("bad")
    return len(str(value).strip())
''',
    )
    graph = build_dependency_graph(struct)
    hotspots = find_coupling_hotspots(graph, threshold=1)

    coupled = {m for h in hotspots for m in h["coupled_to"]}
    spurious = coupled & {
        "str", "len", "isinstance", "ValueError", "logger",
        "logging", "strip", "getLogger",
    }
    assert not spurious, f"builtins/stdlib leaked into coupling graph: {sorted(spurious)}"


def test_graph_nodes_are_only_real_code_entities(tmp_path):
    """Graph nodes should be modules / functions / classes of the codebase,
    not bare builtin names like 'str' or 'round'."""
    struct = _structure_from_source(
        tmp_path,
        beta='''
def compute(xs):
    return round(max(xs), 2)
''',
    )
    graph = build_dependency_graph(struct)
    bad_nodes = {n for n in graph.nodes if n in {"round", "max", "str", "len", "list"}}
    assert not bad_nodes, f"builtin names became graph nodes: {sorted(bad_nodes)}"


def test_cross_module_call_resolution_is_not_name_only(tmp_path):
    """Two modules each defining `save()` — a call to `save` in one module
    must not silently resolve to the other module's `save`."""
    struct = _structure_from_source(
        tmp_path,
        users='''
def save():
    return "users"

def create():
    return save()
''',
        orders='''
def save():
    return "orders"
''',
    )
    graph = build_dependency_graph(struct)
    # users.create -> users.save is correct; users.create -> orders.save is the bug
    assert not graph.has_edge("users.create", "orders.save"), (
        "call to local `save` mis-resolved to another module's function"
    )
