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
import sys
import time
import threading
import numpy as np
from typing import Any, Optional
class TTLCache:
    """Thread-safe TTL in-memory store."""
    def __init__(self, ttl_seconds: int = 600, max_entries: int = 64, max_bytes: int = 256*1024*1024):
        self._ttl   = ttl_seconds
        self._max   = max_entries
        self._max_bytes = max_bytes
        self._store: dict = {}   # key → (value, expire_at)
        self._lock  = threading.Lock()
        self._current_bytes = 0  # Approximate size in bytes of stored values

    def _sizeof(self, value) -> int:
        """Rough size estimate — works for dicts of numpy arrays."""
        if isinstance(value, dict):
            return sum(self._sizeof(v) for v in value.values())
        if isinstance(value, np.ndarray):
            return value.nbytes
        return sys.getsizeof(value)

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
        entry_bytes = self._sizeof(value)
        with self._lock:
            # Don't cache entries larger than 1/4 of budget
            if entry_bytes > self._max_bytes // 4:
                return
            self._evict_expired()
            # Evict until we have room
            while (self._current_bytes + entry_bytes > self._max_bytes 
                   or len(self._store) >= self._max) and self._store:
                oldest = min(self._store, key=lambda k: self._store[k][1])
                _, (old_val, _) = self._store.popitem() if False else (oldest, self._store.pop(oldest))
                self._current_bytes -= self._sizeof(old_val)
            self._store[key] = (value, time.monotonic() + self._ttl)
            self._current_bytes += entry_bytes
 
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
            val, _ = self._store.pop(k)
            self._current_bytes -= self._sizeof(val)
 
 
# ── Module-level singleton ─────────────────────────────────────────────────────
# Import and reuse this instance across the application.
gee_cache = TTLCache(ttl_seconds=900, max_entries=4, max_bytes=200*1024*1024)   # 15-min TTL