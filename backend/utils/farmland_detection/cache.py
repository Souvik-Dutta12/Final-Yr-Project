"""
Lightweight in-memory TTL cache.
 
Avoids redundant Google Earth Engine calls for the same polygon within
a configurable time window.  Thread-safe via a simple lock.
 
Usage
-----
    cache = TTLCache(ttl_seconds=600)  # 10-minute window
 
    key = cache.make_key(polygon, days_back=30)
    result = cache.get(key)
    if result is None:
        result = expensive_gee_call(...)
        cache.set(key, result)
"""

import hashlib
import json
import time
import threading
from typing import Any, Optional

class TTLCache:
    """Thread-safe TTL in-memory store."""
    def __init__(self, ttl_seconds: int = 600, max_entries: int = 64):
        self._ttl   = ttl_seconds
        self._max   = max_entries
        self._store: dict = {}   # key → (value, expire_at)
        self._lock  = threading.Lock()


    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if time.monotonic() > expire_at:
                del self._store[key]
                return None
            return value
 
    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._evict_expired()
            if len(self._store) >= self._max:
                # Evict oldest entry (LRU-lite: just remove one expired or oldest)
                oldest = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest]
            self._store[key] = (value, time.monotonic() + self._ttl)
 
    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
 
    def clear(self) -> None:
        with self._lock:
            self._store.clear()
 
    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """Stable SHA-256 key from arbitrary JSON-serialisable arguments."""
        payload = json.dumps({"args": args, "kwargs": kwargs},
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]
    
    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
 
 
# ── Module-level singleton ─────────────────────────────────────────────────────
# Import and reuse this instance across the application.
gee_cache = TTLCache(ttl_seconds=900, max_entries=32)   # 15-min TTL