"""
RAG — Knowledge Base Loader & Indexer
========================================
Loads curated markdown documents and indexes them into ChromaDB.
Uses file/class-level chunking, NOT token-count chunking.
Per CONTEXT.md §15: token-count chunking splits functions mid-definition.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import Config
from rag.vector_store import VectorStore

logger = logging.getLogger("rag.knowledge_base")


class KnowledgeBase:
    """Manages the curated knowledge base for RAG retrieval.

    Loads markdown documents from the knowledge_base/ directory,
    chunks them semantically, and indexes into ChromaDB.

    Per IMPLEMENTATION_PLAN_v2.md §2:
    - Start with ~50-80 hand-picked docs
    - Only refactoring_patterns + fastapi_patterns initially
    - Add ddd_patterns in Week 3, testing_patterns in Week 7
    """

    def __init__(self, vector_store: Optional[VectorStore] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.vector_store = vector_store or VectorStore(self.config)

    def load_and_index(self, docs_directory: Optional[str] = None) -> Dict[str, int]:
        """Load all documents from the KB directory and index them.

        Args:
            docs_directory: Path to knowledge_base/ directory

        Returns:
            Dict with category -> count of indexed documents
        """
        docs_dir = Path(docs_directory or self.config.kb_docs_directory)

        if not docs_dir.exists():
            logger.warning(f"Knowledge base directory not found: {docs_dir}")
            return {}

        stats = {}
        all_documents = []
        all_metadatas = []
        all_ids = []

        # Walk through category subdirectories
        for category_dir in sorted(docs_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue

            category = category_dir.name
            doc_count = 0

            for doc_file in sorted(category_dir.rglob("*.md")):
                try:
                    content = doc_file.read_text(encoding="utf-8", errors="replace")
                    chunks = self._chunk_document(content, category, doc_file.stem)

                    for i, chunk in enumerate(chunks):
                        doc_id = self._generate_id(category, doc_file.stem, i)
                        all_documents.append(chunk["content"])
                        all_metadatas.append(chunk["metadata"])
                        all_ids.append(doc_id)
                        doc_count += 1

                except Exception as e:
                    logger.warning(f"Failed to process {doc_file}: {e}")

            stats[category] = doc_count
            logger.info(f"Loaded {doc_count} chunks from '{category}'")

        # Batch index
        if all_documents:
            self.vector_store.add_documents(all_documents, all_metadatas, all_ids)
            logger.info(f"Indexed {len(all_documents)} total chunks across {len(stats)} categories")

        return stats

    def _chunk_document(
        self, content: str, category: str, doc_name: str
    ) -> List[Dict[str, Any]]:
        """Chunk a document by logical sections.

        Uses file/class-level chunking per CONTEXT.md §15 —
        NOT token-count chunking which splits functions mid-definition.
        """
        chunks = []
        sections = self._split_by_sections(content)

        for i, section in enumerate(sections):
            # Skip very short sections
            if len(section["content"].strip()) < 50:
                continue

            chunk_content = section["content"]

            # Add section header context
            if section["title"]:
                chunk_content = f"[{category}] {section['title']}\n\n{chunk_content}"

            # Enforce max chunk size (~500 tokens ≈ ~2000 chars)
            if len(chunk_content) > 2000:
                sub_chunks = self._split_long_section(chunk_content, 2000)
                for j, sub in enumerate(sub_chunks):
                    chunks.append({
                        "content": sub,
                        "metadata": {
                            "category": category,
                            "document": doc_name,
                            "section": section["title"] or f"section_{i}",
                            "chunk_index": j,
                        }
                    })
            else:
                chunks.append({
                    "content": chunk_content,
                    "metadata": {
                        "category": category,
                        "document": doc_name,
                        "section": section["title"] or f"section_{i}",
                        "chunk_index": 0,
                    }
                })

        # If no sections found, treat whole doc as one chunk
        if not chunks and content.strip():
            chunks.append({
                "content": f"[{category}] {doc_name}\n\n{content[:2000]}",
                "metadata": {
                    "category": category,
                    "document": doc_name,
                    "section": "full",
                    "chunk_index": 0,
                }
            })

        return chunks

    def _split_by_sections(self, content: str) -> List[Dict[str, Any]]:
        """Split markdown content by header sections.

        Preserves code blocks as atomic units.
        """
        lines = content.split("\n")
        sections = []
        current_title = ""
        current_lines = []

        for line in lines:
            # Check for markdown headers
            if line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
                # Save previous section
                if current_lines:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_lines),
                    })
                current_title = line.lstrip("#").strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # Save last section
        if current_lines:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_lines),
            })

        return sections

    def _split_long_section(self, content: str, max_chars: int) -> List[str]:
        """Split a long section while preserving code block integrity."""
        chunks = []
        lines = content.split("\n")
        current_chunk = []
        current_length = 0
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block

            line_length = len(line) + 1  # +1 for newline

            if current_length + line_length > max_chars and not in_code_block:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _generate_id(self, category: str, doc_name: str, chunk_index: int) -> str:
        """Generate a unique, deterministic document ID."""
        raw = f"{category}:{doc_name}:{chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return self.vector_store.get_collection_stats()
