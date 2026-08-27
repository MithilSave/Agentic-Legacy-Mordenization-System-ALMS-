"""
RAG — Vector Store (ChromaDB)
===============================
Local persistent ChromaDB integration with nomic-embed-text via Ollama.
Per CONTEXT.md: no Pinecone, no cloud calls.
"""

import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
import ollama as ollama_client

from core.config import Config

logger = logging.getLogger("rag.vector_store")


class VectorStore:
    """ChromaDB-backed vector store with Ollama embeddings.

    Uses:
    - ChromaDB local persistent client (./chroma_db)
    - nomic-embed-text embeddings via Ollama
    - Cosine similarity with threshold ≥ 0.70
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._client = None
        self._collection = None

    @property
    def client(self):
        """Lazy-initialize ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.config.chromadb_persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB initialized at: {self.config.chromadb_persist_dir}")
        return self._client

    @property
    def collection(self):
        """Get or create the main collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.config.chromadb_collection,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Collection '{self.config.chromadb_collection}' ready "
                f"({self._collection.count()} documents)"
            )
        return self._collection

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama's nomic-embed-text.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: if the embedding backend errors or returns an
                empty/malformed response. Never substitutes a zero vector —
                a silent zero would corrupt both indexing and query ranking.
        """
        embeddings = []
        for text in texts:
            try:
                response = ollama_client.embed(
                    model=self.config.embedding_model,
                    input=text,
                )
            except Exception as e:
                logger.error(f"Embedding failed: {e}")
                raise RuntimeError(
                    f"Embedding backend '{self.config.embedding_model}' failed: {e}"
                ) from e

            # ollama.embed returns {"embeddings": [[...]]}
            vector = None
            if response and response.get("embeddings"):
                vector = response["embeddings"][0]
            if not vector:
                raise RuntimeError(
                    f"Empty embedding response for text: {text[:50]!r} "
                    f"(model '{self.config.embedding_model}')"
                )
            embeddings.append(vector)

        return embeddings

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> int:
        """Index documents into ChromaDB.

        Args:
            documents: Text content of each document
            metadatas: Metadata dicts (must include 'category')
            ids: Unique document IDs

        Returns:
            Number of documents added
        """
        if not documents:
            return 0

        # Generate embeddings
        logger.info(f"Embedding {len(documents)} documents...")
        embeddings = self.embed_texts(documents)

        # Upsert into ChromaDB
        self.collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Added {len(documents)} documents to collection")
        return len(documents)

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        category_filter: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant documents by semantic similarity.

        Args:
            query_text: The search query
            top_k: Number of results to return
            category_filter: Optional category to filter by
            threshold: Minimum cosine similarity (default: from config)

        Returns:
            List of result dicts with 'content', 'metadata', 'score'
        """
        threshold = threshold or self.config.rag_relevance_threshold

        # Build where filter
        where_filter = None
        if category_filter:
            where_filter = {"category": category_filter}

        # Generate query embedding. A retrieval failure degrades to "no
        # results" (logged) rather than aborting the caller; indexing, by
        # contrast, hard-fails in add_documents so bad vectors never persist.
        try:
            query_embedding = self.embed_texts([query_text])[0]
        except RuntimeError as e:
            logger.error(f"Query embedding failed: {e}")
            return []

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self.collection.count() or 1),
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

        # Process results
        output = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                # ChromaDB returns distances (lower = more similar for cosine)
                distance = results["distances"][0][i] if results["distances"] else 1.0
                similarity = 1.0 - distance  # Convert distance to similarity

                if similarity >= threshold:
                    output.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": round(similarity, 4),
                    })

        # Sort by score descending
        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the current collection."""
        count = self.collection.count()
        return {
            "collection_name": self.config.chromadb_collection,
            "total_documents": count,
            "persist_directory": self.config.chromadb_persist_dir,
        }

    def clear(self):
        """Clear all documents from the collection."""
        try:
            self.client.delete_collection(self.config.chromadb_collection)
            self._collection = None
            logger.info("Collection cleared")
        except Exception as e:
            logger.warning(f"Clear failed: {e}")
