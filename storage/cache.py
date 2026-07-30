"""
Storage — DiskCache Wrapper
==============================
Local disk caching keyed on codebase SHA-256 hash.
Per CONTEXT.md §11: no Redis, use DiskCache.
"""

import logging
from typing import Optional, Any

import diskcache

from core.config import Config

logger = logging.getLogger("storage.cache")


class CacheManager:
    """DiskCache wrapper for caching agent outputs.

    Keyed on codebase SHA-256 hash per CONTEXT.md §11.
    Avoids re-running expensive LLM calls for unchanged codebases.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._cache = None

    @property
    def cache(self):
        """Lazy-initialize DiskCache."""
        if self._cache is None:
            self._cache = diskcache.Cache(
                directory=self.config.cache_directory,
                size_limit=self.config.cache_size_limit,
            )
            logger.info(f"DiskCache initialized at: {self.config.cache_directory}")
        return self._cache

    def get(self, key: str) -> Optional[str]:
        """Get a cached value."""
        try:
            value = self.cache.get(key)
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
            return value
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """Set a cached value.

        Args:
            key: Cache key (typically "agent_name:codebase_hash")
            value: Serialized value (JSON string)
            expire: Optional TTL in seconds

        Returns:
            True on success
        """
        try:
            self.cache.set(key, value, expire=expire)
            logger.debug(f"Cache SET: {key}")
            return True
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
            return False

    def invalidate(self, key: str) -> bool:
        """Delete a cached entry."""
        try:
            return self.cache.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    def clear(self):
        """Clear all cached entries."""
        try:
            self.cache.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "directory": self.config.cache_directory,
            "size": self.cache.volume(),
            "count": len(self.cache),
        }

    def close(self):
        """Close the cache."""
        if self._cache:
            self._cache.close()
            self._cache = None
