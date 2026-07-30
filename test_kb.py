"""Test knowledge base initialization and ChromaDB."""
import sys, os
sys.path.insert(0, ".")
os.environ["PYTHONIOENCODING"] = "utf-8"

from core.config import Config
from rag.knowledge_base import KnowledgeBase

print("=" * 60)
print("  TESTING KNOWLEDGE BASE INITIALIZATION")
print("=" * 60)

config = Config()
print(f"  ChromaDB dir: {config.chromadb_persist_dir}")
print(f"  KB docs dir:  {config.kb_docs_directory}")

kb = KnowledgeBase(config=config)
stats = kb.load_and_index()

print(f"\n  Indexed categories:")
total = 0
for category, count in stats.items():
    print(f"    {category}: {count} chunks")
    total += count

print(f"\n  Total chunks indexed: {total}")

# Test retrieval
from rag.vector_store import VectorStore
vs = VectorStore(config)
results = vs.query("Flask to FastAPI migration pattern", top_k=3)
print(f"\n  Test query results: {len(results)}")
for r in results:
    cat = r['metadata'].get('category', '?')
    doc = r['metadata'].get('document', '?')
    print(f"    [{cat}/{doc}] score={r['score']:.3f}")

print(f"\n  Collection stats: {vs.get_collection_stats()}")
print("\n  KB test PASSED")
print("=" * 60)
