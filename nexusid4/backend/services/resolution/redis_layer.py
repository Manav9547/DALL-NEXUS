"""NexusID — Redis Integration Layer.

Provides:
1. Bloom filter for candidate pair deduplication (50M expected pairs)
2. Adapter health heartbeats (30s interval)
3. General caching for model lookups and hot-reload signals

Falls back to in-memory implementations when Redis is not available.
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
import time
from datetime import datetime
from typing import Optional

# ─── Configuration ───────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_ENABLED = bool(REDIS_URL)

_redis_client = None


def get_redis():
    """Get Redis client, or None if not available."""
    global _redis_client
    if not REDIS_ENABLED:
        return None
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


# ─── Bloom Filter ────────────────────────────────────────────────────────────

class BloomFilter:
    """Probabilistic set membership test for pair deduplication.

    Uses Redis bit arrays when available, falls back to a Python set.
    Sized for 50M expected pairs at 0.1% false positive rate.
    """

    def __init__(self, expected_items: int = 50_000_000, fp_rate: float = 0.001,
                 redis_key: str = "nexusid:bloom:pairs"):
        self._redis_key = redis_key
        self._fp_rate = fp_rate

        # Calculate optimal size and hash count
        # m = -(n * ln(p)) / (ln(2)^2)
        self._size = int(-expected_items * math.log(fp_rate) / (math.log(2) ** 2))
        # k = (m/n) * ln(2)
        self._num_hashes = max(1, int((self._size / expected_items) * math.log(2)))

        # Fallback: Python set
        self._fallback_set: set[str] = set()
        self._redis = get_redis()

    def _get_bit_positions(self, item: str) -> list[int]:
        """Compute k hash positions for an item."""
        positions = []
        for i in range(self._num_hashes):
            h = hashlib.sha256(f"{item}:{i}".encode()).hexdigest()
            positions.append(int(h, 16) % self._size)
        return positions

    def add(self, item: str):
        """Add an item to the bloom filter."""
        if self._redis:
            pipe = self._redis.pipeline()
            for pos in self._get_bit_positions(item):
                pipe.setbit(self._redis_key, pos, 1)
            pipe.execute()
        else:
            self._fallback_set.add(item)

    def contains(self, item: str) -> bool:
        """Check if an item might be in the set. No false negatives."""
        if self._redis:
            pipe = self._redis.pipeline()
            for pos in self._get_bit_positions(item):
                pipe.getbit(self._redis_key, pos)
            results = pipe.execute()
            return all(results)
        else:
            return item in self._fallback_set

    def add_if_absent(self, item: str) -> bool:
        """Add item if not already present. Returns True if newly added.

        This is the primary method for pair deduplication:
            canonical_key = f"{min(id_a, id_b)}:{max(id_a, id_b)}"
            if bloom.add_if_absent(canonical_key):
                # New pair — process it
            else:
                # Already seen — skip
        """
        if self.contains(item):
            return False
        self.add(item)
        return True

    def clear(self):
        """Reset the bloom filter."""
        if self._redis:
            self._redis.delete(self._redis_key)
        else:
            self._fallback_set.clear()

    @property
    def stats(self) -> dict:
        return {
            "mode": "redis" if self._redis else "in-memory",
            "size_bits": self._size,
            "num_hashes": self._num_hashes,
            "fp_rate": self._fp_rate,
            "items_approx": len(self._fallback_set) if not self._redis else "unknown",
        }


# ─── Adapter Heartbeats ─────────────────────────────────────────────────────

class AdapterHeartbeat:
    """Adapter health heartbeat system.

    Each adapter heartbeats every 30s to Redis. A monitoring thread
    checks for stale heartbeats and marks adapters as unhealthy.
    Falls back to in-memory timestamps when Redis is not available.
    """

    HEARTBEAT_TTL = 60  # seconds before considered stale
    HEARTBEAT_INTERVAL = 30  # seconds between heartbeats

    def __init__(self):
        self._redis = get_redis()
        self._fallback: dict[str, dict] = {}
        self._lock = threading.Lock()

    def beat(self, source_system: str, record_count: int = 0, error: Optional[str] = None):
        """Record a heartbeat from an adapter."""
        data = {
            "source_system": source_system,
            "timestamp": datetime.utcnow().isoformat(),
            "record_count": record_count,
            "error": error or "",
            "status": "ERROR" if error else "HEALTHY",
        }

        if self._redis:
            import json
            key = f"nexusid:heartbeat:{source_system}"
            self._redis.setex(key, self.HEARTBEAT_TTL, json.dumps(data))
        else:
            with self._lock:
                self._fallback[source_system] = {**data, "_ts": time.time()}

    def check(self, source_system: str) -> dict:
        """Check the health of an adapter."""
        if self._redis:
            import json
            key = f"nexusid:heartbeat:{source_system}"
            raw = self._redis.get(key)
            if raw:
                return {**json.loads(raw), "stale": False}
            return {"source_system": source_system, "status": "STALE", "stale": True}
        else:
            with self._lock:
                data = self._fallback.get(source_system)
                if not data:
                    return {"source_system": source_system, "status": "UNKNOWN", "stale": True}
                age = time.time() - data.get("_ts", 0)
                return {
                    **{k: v for k, v in data.items() if k != "_ts"},
                    "stale": age > self.HEARTBEAT_TTL,
                    "age_seconds": round(age, 1),
                }

    def check_all(self) -> list[dict]:
        """Check all known adapters."""
        systems = ["SHOP_EST", "FACTORIES", "LABOUR", "KSPCB", "GST"]
        return [self.check(s) for s in systems]


# ─── Model Cache ─────────────────────────────────────────────────────────────

class ModelCache:
    """Cache for active model version and hot-reload signals.

    In production: uses Redis pub/sub for hot-reload notifications.
    In dev: uses in-memory state.
    """

    CACHE_KEY = "nexusid:model:active_version"
    RELOAD_CHANNEL = "nexusid:model:reload"

    def __init__(self):
        self._redis = get_redis()
        self._fallback_version: str = "weighted-linear-v1"
        self._model_object: Optional[object] = None
        self._subscribers: list[callable] = []

    def get_active_version(self) -> str:
        """Get the currently active model version."""
        if self._redis:
            version = self._redis.get(self.CACHE_KEY)
            return version or self._fallback_version
        return self._fallback_version

    def set_active_version(self, version: str):
        """Set the active model version (triggers hot-reload in production)."""
        if self._redis:
            self._redis.set(self.CACHE_KEY, version)
            self._redis.publish(self.RELOAD_CHANNEL, version)
        else:
            self._fallback_version = version

        # Notify local subscribers
        for callback in self._subscribers:
            try:
                callback(version)
            except Exception:
                pass

    def on_reload(self, callback: callable):
        """Register a callback for model hot-reload events."""
        self._subscribers.append(callback)

        # In production: also subscribe to Redis pub/sub
        if self._redis:
            def _listen():
                pubsub = self._redis.pubsub()
                pubsub.subscribe(self.RELOAD_CHANNEL)
                for message in pubsub.listen():
                    if message["type"] == "message":
                        callback(message["data"])
            t = threading.Thread(target=_listen, daemon=True)
            t.start()

    def cache_model(self, model_object: object):
        """Cache the loaded model object in memory."""
        self._model_object = model_object

    def get_cached_model(self) -> Optional[object]:
        """Get the cached model object."""
        return self._model_object

    @property
    def stats(self) -> dict:
        return {
            "mode": "redis" if self._redis else "in-memory",
            "active_version": self.get_active_version(),
            "model_cached": self._model_object is not None,
            "subscriber_count": len(self._subscribers),
        }


# ─── General Cache ───────────────────────────────────────────────────────────

class NexusCache:
    """General-purpose cache with TTL. Redis or in-memory."""

    def __init__(self):
        self._redis = get_redis()
        self._fallback: dict[str, tuple[str, float]] = {}  # key -> (value, expiry)

    def get(self, key: str) -> Optional[str]:
        if self._redis:
            return self._redis.get(f"nexusid:cache:{key}")
        entry = self._fallback.get(key)
        if entry and entry[1] > time.time():
            return entry[0]
        return None

    def set(self, key: str, value: str, ttl: int = 300):
        if self._redis:
            self._redis.setex(f"nexusid:cache:{key}", ttl, value)
        else:
            self._fallback[key] = (value, time.time() + ttl)

    def delete(self, key: str):
        if self._redis:
            self._redis.delete(f"nexusid:cache:{key}")
        else:
            self._fallback.pop(key, None)


# ─── Singletons ─────────────────────────────────────────────────────────────

bloom_filter = BloomFilter()
heartbeat = AdapterHeartbeat()
model_cache = ModelCache()
cache = NexusCache()
