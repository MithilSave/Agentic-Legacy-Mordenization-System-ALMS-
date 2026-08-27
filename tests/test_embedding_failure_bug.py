"""Bug-reproduction tests for rag/vector_store.py embed_texts.

embed_texts currently swallows embedding errors and substitutes an
all-zero vector, silently corrupting the index and query ranking.
It must fail loudly instead.
"""

from unittest.mock import patch

import pytest

import rag.vector_store as vs_mod
from rag.vector_store import VectorStore
from core.config import Config


def _store():
    return VectorStore(Config())


def test_embed_raises_when_backend_errors():
    with patch.object(vs_mod.ollama_client, "embed", side_effect=RuntimeError("ollama down")):
        with pytest.raises(Exception) as exc:
            _store().embed_texts(["hello"])
    assert "ollama down" in str(exc.value) or "embed" in str(exc.value).lower()


def test_embed_raises_on_empty_response():
    with patch.object(vs_mod.ollama_client, "embed", return_value={}):
        with pytest.raises(Exception):
            _store().embed_texts(["hello"])


def test_embed_never_returns_zero_vectors():
    """No code path may return an all-zero embedding as if it were real."""
    with patch.object(vs_mod.ollama_client, "embed", side_effect=RuntimeError("boom")):
        try:
            out = _store().embed_texts(["a", "b"])
        except Exception:
            return  # raising is the correct behaviour
        assert all(any(v != 0.0 for v in vec) for vec in out), "zero vector leaked"
