"""Quick test script to verify the code analysis tool works on the sample monolith."""
import sys
sys.path.insert(0, ".")

from tools.code_analysis import (
    extract_code_structure, build_dependency_graph,
    find_coupling_hotspots, find_circular_dependencies,
    compute_codebase_hash
)

print("=" * 60)
print("  TESTING CODE ANALYSIS ON SAMPLE MONOLITH")
print("=" * 60)

# Extract code structure
structure = extract_code_structure("examples/sample_monolith")
stats = structure["stats"]
print(f"\n  Files:     {stats['total_files']}")
print(f"  Lines:     {stats['total_lines']}")
print(f"  Functions: {stats['total_functions']}")
print(f"  Classes:   {stats['total_classes']}")

# Build dependency graph
graph = build_dependency_graph(structure)
print(f"\n  Graph nodes: {graph.number_of_nodes()}")
print(f"  Graph edges: {graph.number_of_edges()}")

# Find hotspots
hotspots = find_coupling_hotspots(graph)
print(f"\n  Coupling hotspots: {len(hotspots)}")
for h in hotspots:
    coupled = ", ".join(h["coupled_to"])
    print(f"    [{h['severity']}] {h['module']} -> {coupled}")

# Find circular deps
cycles = find_circular_dependencies(graph)
print(f"\n  Circular dependencies: {len(cycles)}")
for c in cycles[:5]:
    print(f"    Cycle: {' -> '.join(str(x) for x in c)}")

# Codebase hash
code_hash = compute_codebase_hash("examples/sample_monolith")
print(f"\n  Codebase SHA-256: {code_hash[:16]}...")

print("\n  ✓ Code analysis test PASSED")
print("=" * 60)
