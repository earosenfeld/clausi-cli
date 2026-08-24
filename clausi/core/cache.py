"""Local on-disk cache for scan results.

Keeps clausi-scan free/local: an unchanged file re-scanned against the same
regulation/clause-scope/provider/model is served from disk instead of
hitting the AI API again.
"""

import contextlib
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def get_cache_dir() -> Path:
    cache_dir = Path.home() / ".clausi" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class LocalCache:
    """File-based cache keyed by (file content hash, regulation, clauses, provider, model)."""

    def __init__(self, enabled: bool = True, ttl: int = DEFAULT_TTL_SECONDS,
                 cache_dir: Optional[Path] = None):
        self.enabled = enabled
        self.ttl = ttl
        self.cache_dir = cache_dir or get_cache_dir()
        self.hits = 0
        self.misses = 0
        # Scans run on a thread pool, so hit/miss counters and the per-key
        # in-flight locks below both need guarding.
        self._stats_lock = threading.Lock()
        self._key_locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def key_lock(self, cache_key: str):
        """Return a lock serializing work for one cache key.

        Duplicate file content is common in real repos (vendored copies,
        repeated boilerplate) and hashes to a single key. Without this, every
        copy misses the cache simultaneously and pays for its own API call.
        """
        if not self.enabled:
            # Nothing to share, so don't serialize unrelated work.
            return contextlib.nullcontext()
        with self._registry_lock:
            return self._key_locks.setdefault(cache_key, threading.Lock())

    def _read(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Read an unexpired entry, without touching hit/miss stats."""
        path = self._path_for(cache_key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() - entry.get("cached_at", 0) > self.ttl:
            return None
        return entry

    def peek(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Re-check the cache after waiting on key_lock.

        This is the second half of one logical lookup, so a hit here converts
        the miss the caller already recorded rather than adding to the total -
        otherwise a deduplicated file counts twice and the reported hit rate
        is computed against an inflated denominator.
        """
        if not self.enabled:
            return None
        entry = self._read(cache_key)
        if entry is None:
            return None
        with self._stats_lock:
            self.hits += 1
            if self.misses:
                self.misses -= 1
        result = entry["result"]
        result["cached"] = True
        return result

    def generate_cache_key(self, file_content: str, regulation: str,
                            clauses: Optional[List[str]] = None,
                            provider: str = "", model: str = "") -> str:
        content_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()[:16]
        key_parts = [content_hash, regulation.replace(" ", "_").lower(), provider, model]
        if clauses:
            clause_hash = hashlib.sha256("_".join(sorted(clauses)).encode("utf-8")).hexdigest()[:8]
            key_parts.append(clause_hash)
        return "scan_" + "_".join(key_parts)

    def _path_for(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        entry = self._read(cache_key)
        if entry is None:
            with self._stats_lock:
                self.misses += 1
            return None

        with self._stats_lock:
            self.hits += 1
        result = entry["result"]
        result["cached"] = True
        return result

    def set(self, cache_key: str, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        entry = {"cached_at": time.time(), "result": result}
        path = self._path_for(cache_key)
        try:
            # Write-then-rename: a plain open("w") from concurrent workers can
            # interleave and leave a truncated file that every later read
            # discards, silently turning a cache hit into a paid API call.
            # os.replace is atomic on POSIX and Windows alike.
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.cache_dir), prefix=f".{cache_key}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(entry, f)
                os.replace(tmp_path, path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
                raise
        except OSError:
            pass

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        return {
            "total_files": total,
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "cache_hit_rate": (self.hits / total) if total else 0.0,
        }

    def clear(self) -> int:
        """Delete all cached entries. Returns count removed."""
        count = 0
        for f in self.cache_dir.glob("scan_*.json"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
        return count
