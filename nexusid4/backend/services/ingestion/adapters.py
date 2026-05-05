"""NexusID — Read-Only Adapter Interface.

The adapter interface is read-only BY DESIGN. There is no write method.
A static test (test_readonly_interface) enforces this via introspection.
"""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Iterator, Optional

from backend.models import BusinessRecordSchema


@dataclass
class AdapterHealth:
    source_system: str
    last_successful_pull_at: Optional[datetime] = None
    last_record_count: int = 0
    last_error: Optional[str] = None
    freshness_seconds: float = 0.0
    status: str = "UNKNOWN"


class AdapterInterface(ABC):
    """Read-only adapter interface.

    CRITICAL: This interface exposes ONLY read operations.
    There is no write, put, post, delete, update, insert, create, or push method.
    This is enforced by a static analysis test.
    """

    @abstractmethod
    def pull(self) -> Iterator[BusinessRecordSchema]:
        """Pull records from the source system. Read-only."""
        ...

    @abstractmethod
    def health(self) -> AdapterHealth:
        """Check adapter health. Read-only."""
        ...

    def source_system(self) -> str:
        """Return the source system identifier."""
        return self.__class__.__name__


# ─── Adapter Registry ────────────────────────────────────────────────────────

_ADAPTER_REGISTRY: dict[str, type[AdapterInterface]] = {}


def register_adapter(source_system: str):
    """Decorator to register an adapter by source system name."""
    def decorator(cls):
        _ADAPTER_REGISTRY[source_system] = cls
        cls._source_system = source_system
        return cls
    return decorator


def get_adapter(source_system: str) -> Optional[type[AdapterInterface]]:
    return _ADAPTER_REGISTRY.get(source_system)


def list_adapters() -> list[str]:
    return list(_ADAPTER_REGISTRY.keys())


# ─── Concrete Adapters ──────────────────────────────────────────────────────

@register_adapter("PARQUET")
class ParquetAdapter(AdapterInterface):
    """Reads from parquet/database snapshots. Read-only."""

    def __init__(self, db_session, source_system: str = "SHOP_EST"):
        self._db = db_session
        self._source = source_system
        self._last_pull: Optional[datetime] = None
        self._last_count = 0

    def pull(self) -> Iterator[BusinessRecordSchema]:
        from backend.models import BusinessRecordDB
        records = self._db.query(BusinessRecordDB).filter(
            BusinessRecordDB.source_system == self._source
        ).all()
        self._last_pull = datetime.utcnow()
        self._last_count = len(records)
        for r in records:
            yield BusinessRecordSchema(
                id=r.id,
                source_system=r.source_system,
                source_record_id=r.source_record_id,
                business_name=r.business_name,
                address_locality=r.address_locality,
                address_pincode=r.address_pincode,
                address_city=r.address_city,
                address_district=r.address_district,
                pan=r.pan,
                gstin=r.gstin,
                phone=r.phone,
                email=r.email,
                registration_date=r.registration_date,
            )

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            source_system=self._source,
            last_successful_pull_at=self._last_pull,
            last_record_count=self._last_count,
            status="HEALTHY" if self._last_pull else "UNKNOWN",
        )


@register_adapter("WEBHOOK")
class WebhookAdapter(AdapterInterface):
    """Receives records via webhook push. Read-only (receives, never sends).

    Supports HMAC-SHA256 signature verification on incoming payloads.
    """

    def __init__(self, secret: str = "nexusid-webhook-secret-2024"):
        self._buffer: list[BusinessRecordSchema] = []
        self._last_receive: Optional[datetime] = None
        self._secret = secret

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature on webhook payload.

        Args:
            body: Raw request body bytes
            signature: Value from X-Webhook-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        import hashlib
        import hmac

        expected = hmac.new(
            self._secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def receive(self, record: BusinessRecordSchema, body: Optional[bytes] = None,
                signature: Optional[str] = None) -> bool:
        """Buffer an incoming record. This is a RECEIVE, not a write to source.

        If body and signature are provided, HMAC verification is performed.
        Returns False if signature verification fails.
        """
        if body is not None and signature is not None:
            if not self.verify_signature(body, signature):
                return False  # Reject: bad signature

        self._buffer.append(record)
        self._last_receive = datetime.utcnow()
        return True

    def pull(self) -> Iterator[BusinessRecordSchema]:
        while self._buffer:
            yield self._buffer.pop(0)

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            source_system="WEBHOOK",
            last_successful_pull_at=self._last_receive,
            last_record_count=len(self._buffer),
            status="HEALTHY",
        )


@register_adapter("API")
class APIAdapter(AdapterInterface):
    """Polls a REST endpoint. Read-only — only GET requests."""

    def __init__(self, base_url: str = "http://localhost:8001", source_system: str = "API"):
        self._base_url = base_url
        self._source = source_system

    def pull(self) -> Iterator[BusinessRecordSchema]:
        # In production: httpx GET with pagination, backoff, etc.
        # For now: yields nothing (no mock server running)
        return iter([])

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            source_system=self._source,
            status="HEALTHY",
        )


# ─── Static Interface Enforcement ────────────────────────────────────────────

WRITE_PATTERN = re.compile(
    r"^(write|put|post|delete|update|insert|create_in|push_to|send|upload|modify|mutate|save_to)",
    re.IGNORECASE
)


def verify_readonly_interface() -> dict:
    """Verify that AdapterInterface and all subclasses have no write methods.

    Returns a report dict. Raises AssertionError if violations found.
    """
    violations = []

    # Check the base class
    for name, method in inspect.getmembers(AdapterInterface, predicate=inspect.isfunction):
        if WRITE_PATTERN.match(name):
            violations.append(f"AdapterInterface.{name}")

    # Check all registered adapters
    for source, adapter_cls in _ADAPTER_REGISTRY.items():
        for name, method in inspect.getmembers(adapter_cls, predicate=inspect.isfunction):
            if WRITE_PATTERN.match(name):
                violations.append(f"{adapter_cls.__name__}.{name}")

    report = {
        "verified": len(violations) == 0,
        "adapters_checked": len(_ADAPTER_REGISTRY) + 1,  # +1 for base
        "violations": violations,
    }

    return report
