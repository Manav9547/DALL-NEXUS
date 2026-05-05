"""NexusID — Core database models and Pydantic schemas."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Date, Text, JSON,
    ForeignKey, Enum as SAEnum, Index, UniqueConstraint, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session, sessionmaker


# ─── Enums ────────────────────────────────────────────────────────────────────

class SourceSystem(str, Enum):
    SHOP_EST = "SHOP_EST"
    FACTORIES = "FACTORIES"
    LABOUR = "LABOUR"
    KSPCB = "KSPCB"
    GST = "GST"


class ActivityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    CLOSED = "CLOSED"


class DecisionType(str, Enum):
    AUTO_LINK = "AUTO_LINK"
    REVIEW = "REVIEW"
    HOLD = "HOLD"


class ReviewDecisionType(str, Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class SignalClass(str, Enum):
    STRONG_ACTIVE = "STRONG_ACTIVE"
    WEAK_ACTIVE = "WEAK_ACTIVE"
    NEUTRAL = "NEUTRAL"
    DORMANCY = "DORMANCY"
    CLOSURE = "CLOSURE"


class EventType(str, Enum):
    LICENCE_RENEWAL = "LICENCE_RENEWAL"
    GST_FILING = "GST_FILING"
    INSPECTION = "INSPECTION"
    COMPLIANCE_NOTICE = "COMPLIANCE_NOTICE"
    CLOSURE_CERT = "CLOSURE_CERT"
    ELECTRICITY_DISCONNECT = "ELECTRICITY_DISCONNECT"
    ANNUAL_RETURN = "ANNUAL_RETURN"
    TAX_PAYMENT = "TAX_PAYMENT"
    POLLUTION_CLEARANCE = "POLLUTION_CLEARANCE"
    LABOUR_COMPLIANCE = "LABOUR_COMPLIANCE"


class AnchorType(str, Enum):
    PAN = "PAN"
    GSTIN = "GSTIN"
    INTERNAL = "INTERNAL"


class AggregateType(str, Enum):
    UBID = "UBID"
    EVENT = "EVENT"
    DECISION = "DECISION"
    REVIEW = "REVIEW"
    MERGE = "MERGE"
    REVERSAL = "REVERSAL"
    STATUS = "STATUS"


# ─── SQLAlchemy Base ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── SQLAlchemy ORM Models ───────────────────────────────────────────────────

class BusinessRecordDB(Base):
    __tablename__ = "business_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_system = Column(String, nullable=False, index=True)
    source_record_id = Column(String, nullable=False)
    business_name = Column(String, nullable=False)
    address_line = Column(String, default="")
    address_locality = Column(String, default="")
    address_city = Column(String, default="")
    address_district = Column(String, default="")
    address_pincode = Column(String, default="")
    address_state = Column(String, default="Karnataka")
    pan = Column(String, nullable=True, index=True)
    gstin = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    registration_date = Column(Date, nullable=True)
    registration_type = Column(String, nullable=True)
    content_hash = Column(String, nullable=False)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    gt_id = Column(String, nullable=True)  # ground truth id (synthetic only)

    __table_args__ = (
        UniqueConstraint("source_system", "source_record_id", name="uq_source_record"),
        Index("ix_content_hash", "content_hash"),
    )


class UBIDMaster(Base):
    __tablename__ = "ubid_master"

    ubid = Column(String, primary_key=True)
    anchor_type = Column(String, nullable=False)
    anchor_value = Column(String, nullable=True)
    primary_name = Column(String, nullable=True)
    primary_address = Column(String, nullable=True)
    primary_pincode = Column(String, nullable=True)
    primary_district = Column(String, nullable=True)
    status = Column(String, default="ACTIVE")  # ACTIVE or DEPRECATED
    deprecated_by_ubid = Column(String, ForeignKey("ubid_master.ubid"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_records = relationship("UBIDSourceRecord", back_populates="ubid_master")


class UBIDSourceRecord(Base):
    __tablename__ = "ubid_source_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ubid = Column(String, ForeignKey("ubid_master.ubid"), nullable=False, index=True)
    source_system = Column(String, nullable=False)
    source_record_id = Column(String, nullable=False)
    record_id = Column(String, nullable=False)  # FK to business_records.id
    content_hash = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    ubid_master = relationship("UBIDMaster", back_populates="source_records")

    __table_args__ = (
        UniqueConstraint("source_system", "source_record_id", name="uq_ubid_source"),
    )


class MergeProvenance(Base):
    __tablename__ = "merge_provenance"

    merge_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ubid_winner = Column(String, ForeignKey("ubid_master.ubid"), nullable=False)
    ubid_loser = Column(String, ForeignKey("ubid_master.ubid"), nullable=False)
    score = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    decided_by = Column(String, default="SYSTEM")
    decided_at = Column(DateTime, default=datetime.utcnow)
    feature_breakdown = Column(JSON, nullable=True)
    reversed = Column(Boolean, default=False)


class MergeReversal(Base):
    __tablename__ = "merge_reversals"

    reversal_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    merge_id = Column(String, ForeignKey("merge_provenance.merge_id"), nullable=False)
    reason = Column(Text, nullable=False)
    reversed_by = Column(String, nullable=False)
    reversed_at = Column(DateTime, default=datetime.utcnow)


class CandidatePairDB(Base):
    __tablename__ = "candidate_pairs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    record_a_id = Column(String, ForeignKey("business_records.id"), nullable=False)
    record_b_id = Column(String, ForeignKey("business_records.id"), nullable=False)
    blocking_keys = Column(JSON, nullable=True)
    score = Column(Float, nullable=True)
    decision = Column(String, nullable=True)
    feature_breakdown = Column(JSON, nullable=True)
    model_version = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    review_status = Column(String, default="PENDING")  # PENDING, CONFIRMED, REJECTED, ESCALATED
    reviewer_id = Column(String, nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_candidate_decision", "decision"),
        Index("ix_candidate_review", "review_status"),
    )


class ActivityEventDB(Base):
    __tablename__ = "activity_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ubid = Column(String, ForeignKey("ubid_master.ubid"), nullable=True, index=True)
    source_system = Column(String, nullable=False)
    source_event_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    signal_class = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    payload = Column(JSON, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    joined_at = Column(DateTime, nullable=True)


class ActivityStatusCurrent(Base):
    __tablename__ = "activity_status_current"

    ubid = Column(String, ForeignKey("ubid_master.ubid"), primary_key=True)
    status = Column(String, nullable=False, default="ACTIVE")
    score = Column(Float, default=0.0)
    last_strong_active_at = Column(DateTime, nullable=True)
    status_since = Column(DateTime, default=datetime.utcnow)
    last_recomputed_at = Column(DateTime, default=datetime.utcnow)
    event_count = Column(Integer, default=0)
    last_event_date = Column(Date, nullable=True)


class EventLedger(Base):
    __tablename__ = "event_ledger"

    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QueryAudit(Base):
    __tablename__ = "query_audit"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    query_type = Column(String, nullable=False)
    query_params = Column(JSON, nullable=True)
    result_count = Column(Integer, default=0)
    latency_ms = Column(Float, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)


class AdapterHealthDB(Base):
    __tablename__ = "adapter_health"

    source_system = Column(String, primary_key=True)
    last_successful_pull_at = Column(DateTime, nullable=True)
    last_record_count = Column(Integer, default=0)
    total_records = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    freshness_seconds = Column(Float, default=0)
    status = Column(String, default="HEALTHY")
    updated_at = Column(DateTime, default=datetime.utcnow)


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class BusinessRecordSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_system: str
    source_record_id: str
    business_name: str
    address_line: str = ""
    address_locality: str = ""
    address_city: str = ""
    address_district: str = ""
    address_pincode: str = ""
    address_state: str = "Karnataka"
    pan: Optional[str] = None
    gstin: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    registration_date: Optional[date] = None
    registration_type: Optional[str] = None
    gt_id: Optional[str] = None

    def content_hash(self) -> str:
        data = json.dumps({
            "source_system": self.source_system,
            "business_name": self.business_name.lower().strip(),
            "pincode": self.address_pincode,
            "pan": self.pan,
            "gstin": self.gstin,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class FeatureVector(BaseModel):
    anchor_score: float = 0.0
    name_score: float = 0.0
    address_score: float = 0.0
    contact_score: float = 0.0
    date_proximity_score: float = 0.0

    def to_dict(self) -> dict:
        return self.model_dump()


class CandidatePairSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_a_id: str
    record_b_id: str
    blocking_keys: list[str] = []
    score: Optional[float] = None
    decision: Optional[str] = None
    feature_breakdown: Optional[dict] = None
    model_version: Optional[str] = None
    review_status: str = "PENDING"


class ReviewDecisionSchema(BaseModel):
    decision: ReviewDecisionType
    reviewer_id: str
    notes: Optional[str] = None


class UBIDDetail(BaseModel):
    ubid: str
    anchor_type: str
    anchor_value: Optional[str]
    primary_name: Optional[str]
    primary_address: Optional[str]
    primary_pincode: Optional[str]
    primary_district: Optional[str]
    status: str
    source_record_count: int = 0
    created_at: Optional[datetime] = None


class ActivityEventSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ubid: Optional[str] = None
    source_system: str
    source_event_id: str
    event_type: str
    signal_class: str
    event_date: date
    payload: Optional[dict] = None


class TimelineEntry(BaseModel):
    event_id: str
    event_date: date
    source_system: str
    event_type: str
    signal_class: str
    base_weight: float
    decayed_weight: float
    is_tipping_point: bool = False


class LedgerEntry(BaseModel):
    ledger_id: int
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict
    prev_hash: str
    hash: str
    created_at: datetime


class SystemStats(BaseModel):
    total_records: int = 0
    total_ubids: int = 0
    total_merges: int = 0
    total_events: int = 0
    active_businesses: int = 0
    dormant_businesses: int = 0
    closed_businesses: int = 0
    review_queue_depth: int = 0
    auto_link_rate: float = 0.0
    avg_score: float = 0.0
    departments_connected: int = 5
    ledger_entries: int = 0


# ─── Database Setup ──────────────────────────────────────────────────────────

import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nexusid.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_db():
    """FastAPI dependency for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
