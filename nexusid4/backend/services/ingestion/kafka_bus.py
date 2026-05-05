"""NexusID — Kafka Integration Layer.

Provides Kafka producers and consumers for all pipeline topics.
Falls back to an in-memory queue when Kafka is not available,
so the system works both in production (with Kafka) and in
demo mode (without any infrastructure).

Topics:
  business.records.raw          — raw records from adapters
  business.records.canonical    — normalized records
  resolution.candidates         — candidate pairs from blocking
  resolution.auto-link          — auto-linked pairs
  resolution.review-queue       — pairs for human review
  resolution.hold-separate      — pairs below threshold
  resolution.anchor-conflict    — conflicting PAN/GSTIN pairs
  resolution.review-confirmed   — reviewer confirmations
  resolution.review-rejected    — reviewer rejections
  ubid.events                   — UBID lifecycle events
  activity.status-changes       — status change events
  system.alerts                 — system-wide alerts
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Optional

# ─── Configuration ───────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_ENABLED = bool(KAFKA_BOOTSTRAP)

# Topic definitions with partition counts and retention
TOPIC_CONFIG = {
    "business.records.raw":        {"partitions": 6, "retention_ms": 7 * 86400000},
    "business.records.canonical":  {"partitions": 6, "retention_ms": 30 * 86400000},
    "business.records.dead-letter":{"partitions": 3, "retention_ms": 14 * 86400000},
    "resolution.candidates":      {"partitions": 6, "retention_ms": 7 * 86400000},
    "resolution.auto-link":       {"partitions": 3, "retention_ms": 7 * 86400000},
    "resolution.review-queue":    {"partitions": 3, "retention_ms": 30 * 86400000},
    "resolution.hold-separate":   {"partitions": 3, "retention_ms": 7 * 86400000},
    "resolution.anchor-conflict": {"partitions": 1, "retention_ms": 30 * 86400000},
    "resolution.review-confirmed":{"partitions": 3, "retention_ms": 30 * 86400000},
    "resolution.review-rejected": {"partitions": 3, "retention_ms": 30 * 86400000},
    "ubid.events":                {"partitions": 6, "retention_ms": 90 * 86400000},
    "activity.status-changes":    {"partitions": 6, "retention_ms": 90 * 86400000},
    "system.alerts":              {"partitions": 1, "retention_ms": 30 * 86400000},
}


# ─── In-Memory Fallback ─────────────────────────────────────────────────────

class InMemoryBus:
    """Thread-safe in-memory message bus for demo/dev mode."""

    def __init__(self):
        self._queues: dict[str, list[dict]] = defaultdict(list)
        self._consumers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stats: dict[str, int] = defaultdict(int)

    def produce(self, topic: str, key: Optional[str], value: dict):
        with self._lock:
            msg = {
                "topic": topic,
                "key": key,
                "value": value,
                "timestamp": datetime.utcnow().isoformat(),
                "offset": self._stats[topic],
            }
            self._queues[topic].append(msg)
            self._stats[topic] += 1

            # Notify consumers
            for callback in self._consumers.get(topic, []):
                try:
                    callback(msg)
                except Exception:
                    pass

    def consume(self, topic: str, callback: Callable):
        with self._lock:
            self._consumers[topic].append(callback)

    def get_messages(self, topic: str, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._queues[topic][-limit:])

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "mode": "in-memory",
                "topics": {t: {"messages": len(q), "total_produced": self._stats[t]}
                           for t, q in self._queues.items() if q},
            }


# Singleton
_bus = InMemoryBus()


# ─── Kafka Producer ─────────────────────────────────────────────────────────

class NexusProducer:
    """Kafka producer with in-memory fallback.

    Usage:
        producer = NexusProducer()
        producer.send("resolution.candidates", key=pair_id, value={"record_a": ..., "record_b": ...})
    """

    def __init__(self):
        self._kafka_producer = None
        if KAFKA_ENABLED:
            try:
                from confluent_kafka import Producer
                self._kafka_producer = Producer({
                    "bootstrap.servers": KAFKA_BOOTSTRAP,
                    "acks": "all",
                    "retries": 3,
                    "retry.backoff.ms": 500,
                    "linger.ms": 10,
                    "batch.size": 32768,
                    "compression.type": "lz4",
                    "client.id": "nexusid-producer",
                })
            except ImportError:
                pass

    def send(self, topic: str, key: Optional[str] = None, value: Any = None):
        """Send a message to a topic."""
        serialized = json.dumps(value, default=str) if value else "{}"

        if self._kafka_producer:
            self._kafka_producer.produce(
                topic=topic,
                key=key.encode() if key else None,
                value=serialized.encode(),
                callback=self._delivery_callback,
            )
            self._kafka_producer.poll(0)
        else:
            _bus.produce(topic, key, value or {})

    def flush(self, timeout: float = 5.0):
        """Flush all pending messages."""
        if self._kafka_producer:
            self._kafka_producer.flush(timeout)

    @staticmethod
    def _delivery_callback(err, msg):
        if err:
            import structlog
            log = structlog.get_logger()
            log.error("kafka_delivery_failed", error=str(err), topic=msg.topic())


# ─── Kafka Consumer ─────────────────────────────────────────────────────────

class NexusConsumer:
    """Kafka consumer with in-memory fallback.

    Usage:
        consumer = NexusConsumer(["resolution.candidates"], group_id="scorer")
        for msg in consumer.poll():
            process(msg)
    """

    def __init__(self, topics: list[str], group_id: str = "nexusid"):
        self._topics = topics
        self._kafka_consumer = None

        if KAFKA_ENABLED:
            try:
                from confluent_kafka import Consumer
                self._kafka_consumer = Consumer({
                    "bootstrap.servers": KAFKA_BOOTSTRAP,
                    "group.id": group_id,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": True,
                    "session.timeout.ms": 30000,
                    "client.id": f"nexusid-{group_id}",
                })
                self._kafka_consumer.subscribe(topics)
            except ImportError:
                pass

    def poll(self, timeout: float = 1.0, max_messages: int = 100) -> list[dict]:
        """Poll for new messages."""
        if self._kafka_consumer:
            messages = []
            msg = self._kafka_consumer.poll(timeout)
            if msg and not msg.error():
                try:
                    value = json.loads(msg.value().decode())
                    messages.append({
                        "topic": msg.topic(),
                        "key": msg.key().decode() if msg.key() else None,
                        "value": value,
                        "offset": msg.offset(),
                        "partition": msg.partition(),
                    })
                except Exception:
                    pass
            return messages
        else:
            # In-memory: return recent messages
            result = []
            for topic in self._topics:
                result.extend(_bus.get_messages(topic, max_messages))
            return result[-max_messages:]

    def close(self):
        if self._kafka_consumer:
            self._kafka_consumer.close()


# ─── Topic Initialization ───────────────────────────────────────────────────

def create_topics():
    """Create all Kafka topics (idempotent). No-op in in-memory mode."""
    if not KAFKA_ENABLED:
        return {"mode": "in-memory", "topics_created": 0}

    try:
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
        new_topics = [
            NewTopic(
                topic=name,
                num_partitions=config["partitions"],
                replication_factor=1,
                config={"retention.ms": str(config["retention_ms"])},
            )
            for name, config in TOPIC_CONFIG.items()
        ]

        results = admin.create_topics(new_topics)
        created = sum(1 for f in results.values() if not f.result())
        return {"mode": "kafka", "topics_created": created, "total": len(TOPIC_CONFIG)}

    except Exception as e:
        return {"mode": "kafka", "error": str(e)}


# ─── Pipeline Event Helpers ──────────────────────────────────────────────────

_producer = NexusProducer()


def emit_raw_record(record: dict):
    """Emit a raw business record to the ingestion topic."""
    _producer.send("business.records.raw", key=record.get("id"), value=record)


def emit_canonical_record(record: dict):
    """Emit a canonicalized record."""
    _producer.send("business.records.canonical", key=record.get("id"), value=record)


def emit_candidate_pair(pair: dict):
    """Emit a candidate pair from blocking."""
    _producer.send("resolution.candidates", key=pair.get("id"), value=pair)


def emit_resolution_decision(pair_id: str, decision: str, score: float, features: dict):
    """Emit a resolution decision."""
    topic = {
        "AUTO_LINK": "resolution.auto-link",
        "REVIEW": "resolution.review-queue",
        "HOLD": "resolution.hold-separate",
    }.get(decision, "resolution.hold-separate")
    _producer.send(topic, key=pair_id, value={"score": score, "decision": decision, "features": features})


def emit_ubid_event(ubid: str, event_type: str, payload: dict):
    """Emit a UBID lifecycle event."""
    _producer.send("ubid.events", key=ubid, value={"event_type": event_type, **payload})


def emit_status_change(ubid: str, old_status: str, new_status: str, score: float):
    """Emit a status change event."""
    _producer.send("activity.status-changes", key=ubid, value={
        "old_status": old_status, "new_status": new_status, "score": score,
    })


def emit_system_alert(alert_type: str, message: str, details: Optional[dict] = None):
    """Emit a system alert."""
    _producer.send("system.alerts", key=alert_type, value={"message": message, "details": details or {}})


def get_bus_stats() -> dict:
    """Get message bus statistics."""
    if KAFKA_ENABLED:
        return {"mode": "kafka", "bootstrap": KAFKA_BOOTSTRAP}
    return _bus.get_stats()
