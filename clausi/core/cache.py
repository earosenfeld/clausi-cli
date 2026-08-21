"""Local on-disk cache for scan results.

Keeps clausi-scan free/local: an unchanged file re-scanned against the same
regulation/clause-scope/provider/model is served from disk instead of
hitting the AI API again.
"""

import hashlib
import json
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
        path = self._path_for(cache_key)
        if not path.exists():
            self.misses += 1
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.misses += 1
            return None

        if time.time() - entry.get("cached_at", 0) > self.ttl:
            self.misses += 1
            return None

        self.hits += 1
        result = entry["result"]
        result["cached"] = True
        return result

    def set(self, cache_key: str, result: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        entry = {"cached_at": time.time(), "result": result}
        try:
            with open(self._path_for(cache_key), "w", encoding="utf-8") as f:
                json.dump(entry, f)
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
