"""
Core — Configuration Loader
=============================
Loads config.yaml and provides typed access to all settings.
Source of truth: CONTEXT.md / IMPLEMENTATION_PLAN_v2.md
"""

import os
import yaml
from pathlib import Path


# ──────────────────────────────────────────────
# Default Configuration
# ──────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "ollama": {
        "host": "http://localhost:11434",
        "model": "qwen2.5-coder:7b",
        "embedding_model": "nomic-embed-text",
    },
    "agents": {
        "analyzer": {"num_ctx": 4096, "temperature": 0.05},
        "architect": {"num_ctx": 4096, "temperature": 0.1},
        "refactoring": {"num_ctx": 6144, "temperature": 0.2},
        "test_gen": {"num_ctx": 4096, "temperature": 0.15},
    },
    "chromadb": {
        "persist_directory": "./chroma_db",
        "collection_name": "migration_kb",
    },
    "cache": {
        "directory": "./cache_db",
        "size_limit": 1073741824,
    },
    "rag": {
        "relevance_threshold": 0.70,
        "chunk_size": 500,
        "chunk_overlap": 100,
    },
    "safety": {
        "max_retries": 3,
        "escalate_after_retries": True,
    },
    "audit": {
        "database": "./audit.db",
        "log_level": "INFO",
    },
    "knowledge_base": {
        "docs_directory": "./knowledge_base",
    },
}


class Config:
    """Application configuration manager.

    Loads from config.yaml with fallback to defaults.
    All infrastructure choices follow CONTEXT.md:
    - Ollama (local, no cloud)
    - ChromaDB (local persistent)
    - DiskCache (local)
    - NetworkX (in-memory)
    """

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = self._load_config()

    def _load_config(self):
        """Load configuration from YAML file or use defaults."""
        config_path = self._find_config_file()
        if config_path and config_path.exists():
            with open(config_path, "r") as f:
                file_config = yaml.safe_load(f) or {}
            return self._deep_merge(_DEFAULT_CONFIG, file_config)
        return _DEFAULT_CONFIG.copy()

    def _find_config_file(self):
        """Search for config.yaml in project root."""
        # Check current directory, then parent directories
        search_dirs = [
            Path.cwd(),
            Path(__file__).parent.parent,  # Project root
        ]
        for d in search_dirs:
            config_path = d / "config.yaml"
            if config_path.exists():
                return config_path
        return None

    def _deep_merge(self, base, override):
        """Deep merge override dict into base dict."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # ── Ollama Settings ──

    @property
    def ollama_host(self):
        return self._config["ollama"]["host"]

    @property
    def ollama_model(self):
        return self._config["ollama"]["model"]

    @property
    def embedding_model(self):
        return self._config["ollama"]["embedding_model"]

    # ── Agent Settings ──

    def get_agent_config(self, agent_name):
        """Get configuration for a specific agent.

        Args:
            agent_name: One of 'analyzer', 'architect', 'refactoring', 'test_gen'

        Returns:
            Dict with num_ctx, temperature, rag_categories, rag_top_k
        """
        agents = self._config.get("agents", {})
        agent_cfg = agents.get(agent_name, {})
        return {
            "num_ctx": agent_cfg.get("num_ctx", 4096),
            "temperature": agent_cfg.get("temperature", 0.1),
            "rag_categories": agent_cfg.get("rag_categories", []),
            "rag_top_k": agent_cfg.get("rag_top_k", 3),
            "description": agent_cfg.get("description", ""),
        }

    # ── ChromaDB Settings ──

    @property
    def chromadb_persist_dir(self):
        return self._config["chromadb"]["persist_directory"]

    @property
    def chromadb_collection(self):
        return self._config["chromadb"]["collection_name"]

    # ── Cache Settings ──

    @property
    def cache_directory(self):
        return self._config["cache"]["directory"]

    @property
    def cache_size_limit(self):
        return self._config["cache"]["size_limit"]

    # ── RAG Settings ──

    @property
    def rag_relevance_threshold(self):
        return self._config["rag"]["relevance_threshold"]

    @property
    def rag_chunk_size(self):
        return self._config["rag"]["chunk_size"]

    # ── Safety Settings ──

    @property
    def max_retries(self):
        return self._config["safety"]["max_retries"]

    # ── Audit Settings ──

    @property
    def audit_db_path(self):
        return self._config["audit"]["database"]

    # ── Knowledge Base ──

    @property
    def kb_docs_directory(self):
        return self._config["knowledge_base"]["docs_directory"]

    def __repr__(self):
        return f"Config(model={self.ollama_model}, chromadb={self.chromadb_persist_dir})"
