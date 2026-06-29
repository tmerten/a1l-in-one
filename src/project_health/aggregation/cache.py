"""In-memory TTL cache with per-source invalidation."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float
    sources: frozenset[str]


class AggregationCache:
    """In-memory cache keyed on (endpoint, query params, source set)."""

    def __init__(self, ttl_seconds: int = 900) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def _make_key(self, endpoint: str, params: dict[str, Any], sources: set[str]) -> str:
        param_str = ",".join(f"{k}={v}" for k, v in sorted(params.items()))
        source_str = ",".join(sorted(sources))
        return f"{endpoint}|{param_str}|{source_str}"

    def get(self, endpoint: str, params: dict[str, Any], sources: set[str]) -> Any | None:
        key = self._make_key(endpoint, params, sources)
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, endpoint: str, params: dict[str, Any], sources: set[str], value: Any) -> None:
        key = self._make_key(endpoint, params, sources)
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.time() + self._ttl,
            sources=frozenset(sources),
        )

    def invalidate_source(self, source: str) -> None:
        """Evict all entries whose source set includes the given source."""
        to_delete = [
            key for key, entry in self._store.items()
            if source in entry.sources
        ]
        for key in to_delete:
            del self._store[key]

    def invalidate_all(self) -> None:
        self._store.clear()

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._store)}


# Global singleton cache
cache = AggregationCache(ttl_seconds=900)


def cached_query(
    endpoint: str,
    sources: set[str],
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator to cache aggregation query results."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build params from args/kwargs (simplified)
            params = {**kwargs}
            cached = cache.get(endpoint, params, sources)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            cache.set(endpoint, params, sources, result)
            return result
        return wrapper
    return decorator
