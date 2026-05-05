"""NexusID UBID Registry.

Manages Unified Business IDs, merges, reversals, and the identity graph.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

import networkx as nx
from sqlalchemy.orm import Session

from backend.models import (
    BusinessRecordDB, CandidatePairDB, UBIDMaster, UBIDSourceRecord,
    MergeProvenance, MergeReversal, EventLedger, AnchorType,
    DecisionType
)
from backend.services.resolution.normalize import validate_pan, validate_gstin


# ─── UBID Format ─────────────────────────────────────────────────────────────

def generate_ubid(anchor_type: str, anchor_value: Optional[str] = None) -> str:
    """Generate a new UBID."""
    if anchor_type == AnchorType.PAN.value and anchor_value:
        return f"UBID-PAN-{anchor_value}"
    elif anchor_type == AnchorType.GSTIN.value and anchor_value:
        return f"UBID-GST-{anchor_value}"
    else:
        return f"UBID-INT-{uuid.uuid4().hex[:12].upper()}"


# ─── Ledger Helpers ──────────────────────────────────────────────────────────

def _get_last_hash(db: Session) -> str:
    """Get the hash of the last ledger entry, or genesis hash."""
    last = db.query(EventLedger).order_by(EventLedger.ledger_id.desc()).first()
    return last.hash if last else hashlib.sha256(b"GENESIS").hexdigest()


def _write_ledger(db: Session, event_type: str, aggregate_type: str,
                  aggregate_id: str, payload: dict) -> EventLedger:
    """Append an immutable entry to the event ledger."""
    prev_hash = _get_last_hash(db)
    canonical = json.dumps(payload, sort_keys=True, default=str)
    entry_hash = hashlib.sha256(f"{prev_hash}|{canonical}".encode()).hexdigest()

    entry = EventLedger(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=entry_hash,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()  # Ensure sequential hash chain
    return entry


# ─── Registry Operations ────────────────────────────────────────────────────

def assign_ubid(db: Session, record: BusinessRecordDB) -> str:
    """Assign a UBID to a record. Idempotent.

    If the record already has a UBID assignment, return it.
    If an anchor matches an existing UBID, attach to it.
    Otherwise create a new UBID.
    """
    # Check if already assigned
    existing = db.query(UBIDSourceRecord).filter(
        UBIDSourceRecord.source_system == record.source_system,
        UBIDSourceRecord.source_record_id == record.source_record_id,
    ).first()
    if existing:
        return existing.ubid

    # Try anchor match
    valid_pan, pan = validate_pan(record.pan)
    valid_gstin, gstin = validate_gstin(record.gstin)

    if valid_gstin and gstin:
        existing_ubid = db.query(UBIDMaster).filter(
            UBIDMaster.anchor_type == AnchorType.GSTIN.value,
            UBIDMaster.anchor_value == gstin,
            UBIDMaster.status == "ACTIVE",
        ).first()
        if existing_ubid:
            _attach_record(db, existing_ubid.ubid, record)
            return existing_ubid.ubid

    if valid_pan and pan:
        existing_ubid = db.query(UBIDMaster).filter(
            UBIDMaster.anchor_type == AnchorType.PAN.value,
            UBIDMaster.anchor_value == pan,
            UBIDMaster.status == "ACTIVE",
        ).first()
        if existing_ubid:
            _attach_record(db, existing_ubid.ubid, record)
            return existing_ubid.ubid

    # Create new UBID
    if valid_gstin and gstin:
        ubid = generate_ubid(AnchorType.GSTIN.value, gstin)
        anchor_type = AnchorType.GSTIN.value
        anchor_value = gstin
    elif valid_pan and pan:
        ubid = generate_ubid(AnchorType.PAN.value, pan)
        anchor_type = AnchorType.PAN.value
        anchor_value = pan
    else:
        ubid = generate_ubid(AnchorType.INTERNAL.value)
        anchor_type = AnchorType.INTERNAL.value
        anchor_value = None

    # Avoid duplicate UBID
    if db.query(UBIDMaster).get(ubid):
        ubid = generate_ubid(AnchorType.INTERNAL.value)
        anchor_type = AnchorType.INTERNAL.value
        anchor_value = None

    master = UBIDMaster(
        ubid=ubid,
        anchor_type=anchor_type,
        anchor_value=anchor_value,
        primary_name=record.business_name,
        primary_address=f"{record.address_locality}, {record.address_city}",
        primary_pincode=record.address_pincode,
        primary_district=record.address_district,
        status="ACTIVE",
        created_at=datetime.utcnow(),
    )
    db.add(master)
    db.flush()  # Make visible within session for subsequent anchor lookups
    _attach_record(db, ubid, record)

    _write_ledger(db, "UBID_CREATED", "UBID", ubid, {
        "anchor_type": anchor_type,
        "anchor_value": anchor_value,
        "primary_name": record.business_name,
        "source_system": record.source_system,
        "source_record_id": record.source_record_id,
    })

    return ubid


def _attach_record(db: Session, ubid: str, record: BusinessRecordDB):
    """Attach a source record to a UBID."""
    sr = UBIDSourceRecord(
        ubid=ubid,
        source_system=record.source_system,
        source_record_id=record.source_record_id,
        record_id=record.id,
        content_hash=record.content_hash,
        joined_at=datetime.utcnow(),
    )
    db.add(sr)


def merge_ubids(db: Session, winner_ubid: str, loser_ubid: str,
                score: float, model_version: str,
                decided_by: str = "SYSTEM",
                feature_breakdown: Optional[dict] = None) -> str:
    """Merge loser into winner. Returns winner UBID."""
    winner = db.query(UBIDMaster).get(winner_ubid)
    loser = db.query(UBIDMaster).get(loser_ubid)

    if not winner or not loser:
        raise ValueError(f"UBID not found: winner={winner_ubid}, loser={loser_ubid}")

    if winner.status != "ACTIVE" or loser.status != "ACTIVE":
        return winner_ubid  # Idempotent: already merged

    if winner_ubid == loser_ubid:
        return winner_ubid  # Self-merge: no-op

    # Reassign loser's source records to winner
    loser_records = db.query(UBIDSourceRecord).filter(
        UBIDSourceRecord.ubid == loser_ubid
    ).all()

    for sr in loser_records:
        sr.ubid = winner_ubid

    # Deprecate loser
    loser.status = "DEPRECATED"
    loser.deprecated_by_ubid = winner_ubid

    # Record provenance
    merge = MergeProvenance(
        merge_id=str(uuid.uuid4()),
        ubid_winner=winner_ubid,
        ubid_loser=loser_ubid,
        score=score,
        model_version=model_version,
        decided_by=decided_by,
        decided_at=datetime.utcnow(),
        feature_breakdown=feature_breakdown,
    )
    db.add(merge)

    # Ledger
    _write_ledger(db, "UBID_MERGED", "MERGE", merge.merge_id, {
        "winner": winner_ubid,
        "loser": loser_ubid,
        "score": score,
        "model_version": model_version,
        "decided_by": decided_by,
        "features": feature_breakdown,
    })

    return winner_ubid


def reverse_merge(db: Session, merge_id: str, reason: str, reversed_by: str) -> tuple[str, str]:
    """Reverse a merge. Returns (winner_ubid, restored_loser_ubid)."""
    merge = db.query(MergeProvenance).get(merge_id)
    if not merge:
        raise ValueError(f"Merge not found: {merge_id}")

    if merge.reversed:
        raise ValueError(f"Merge already reversed: {merge_id}")

    # Re-activate the loser UBID
    loser = db.query(UBIDMaster).get(merge.ubid_loser)
    if loser:
        loser.status = "ACTIVE"
        loser.deprecated_by_ubid = None

    # Mark merge as reversed
    merge.reversed = True

    # Create reversal record
    reversal = MergeReversal(
        reversal_id=str(uuid.uuid4()),
        merge_id=merge_id,
        reason=reason,
        reversed_by=reversed_by,
        reversed_at=datetime.utcnow(),
    )
    db.add(reversal)

    # Ledger
    _write_ledger(db, "MERGE_REVERSED", "REVERSAL", reversal.reversal_id, {
        "merge_id": merge_id,
        "winner": merge.ubid_winner,
        "loser": merge.ubid_loser,
        "reason": reason,
        "reversed_by": reversed_by,
    })

    return merge.ubid_winner, merge.ubid_loser


def run_resolution(db: Session) -> dict:
    """Process all auto-link decisions: assign UBIDs and merge where appropriate."""
    # First: assign every record a UBID
    records = db.query(BusinessRecordDB).all()
    ubid_assignments = {}

    for record in records:
        ubid = assign_ubid(db, record)
        ubid_assignments[record.id] = ubid

    db.commit()

    # Then: process auto-link pairs
    auto_pairs = db.query(CandidatePairDB).filter(
        CandidatePairDB.decision == DecisionType.AUTO_LINK.value
    ).order_by(CandidatePairDB.score.desc()).all()

    merges = 0
    for pair in auto_pairs:
        ubid_a = ubid_assignments.get(pair.record_a_id)
        ubid_b = ubid_assignments.get(pair.record_b_id)

        if not ubid_a or not ubid_b or ubid_a == ubid_b:
            continue

        # Resolve to current active UBID (follow deprecation chain)
        ubid_a = _resolve_active(db, ubid_a)
        ubid_b = _resolve_active(db, ubid_b)

        if ubid_a == ubid_b:
            continue

        # Winner is the one with more source records (or the anchored one)
        winner_rec_count = db.query(UBIDSourceRecord).filter(
            UBIDSourceRecord.ubid == ubid_a).count()
        loser_rec_count = db.query(UBIDSourceRecord).filter(
            UBIDSourceRecord.ubid == ubid_b).count()

        if winner_rec_count >= loser_rec_count:
            winner, loser = ubid_a, ubid_b
        else:
            winner, loser = ubid_b, ubid_a

        merge_ubids(db, winner, loser, pair.score or 0.0,
                    pair.model_version or "weighted-linear-v1",
                    feature_breakdown=pair.feature_breakdown)
        merges += 1

        # Update assignments
        for rid, uid in ubid_assignments.items():
            if uid == loser:
                ubid_assignments[rid] = winner

    db.commit()

    active_ubids = db.query(UBIDMaster).filter(UBIDMaster.status == "ACTIVE").count()

    return {
        "records_assigned": len(ubid_assignments),
        "auto_link_pairs": len(auto_pairs),
        "merges_performed": merges,
        "active_ubids": active_ubids,
    }


def _resolve_active(db: Session, ubid: str) -> str:
    """Follow deprecation chain to find the active UBID."""
    seen = set()
    current = ubid
    while current:
        if current in seen:
            break
        seen.add(current)
        master = db.query(UBIDMaster).get(current)
        if not master or master.status == "ACTIVE":
            return current
        if master.deprecated_by_ubid:
            current = master.deprecated_by_ubid
        else:
            return current
    return current


def verify_ledger(db: Session) -> dict:
    """Verify the integrity of the hash-chained event ledger."""
    entries = db.query(EventLedger).order_by(EventLedger.ledger_id).all()

    if not entries:
        return {"verified": True, "entries": 0, "errors": []}

    errors = []
    expected_prev = hashlib.sha256(b"GENESIS").hexdigest()

    for entry in entries:
        # Check prev_hash chain
        if entry.prev_hash != expected_prev:
            errors.append({
                "ledger_id": entry.ledger_id,
                "error": "prev_hash mismatch",
                "expected": expected_prev[:16],
                "actual": entry.prev_hash[:16],
            })

        # Recompute hash
        canonical = json.dumps(entry.payload, sort_keys=True, default=str)
        computed_hash = hashlib.sha256(f"{entry.prev_hash}|{canonical}".encode()).hexdigest()

        if entry.hash != computed_hash:
            errors.append({
                "ledger_id": entry.ledger_id,
                "error": "hash mismatch",
                "computed": computed_hash[:16],
                "stored": entry.hash[:16],
            })

        expected_prev = entry.hash

    return {
        "verified": len(errors) == 0,
        "entries": len(entries),
        "errors": errors,
    }
