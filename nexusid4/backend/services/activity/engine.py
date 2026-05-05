"""NexusID Activity Engine.

Event processing, rolling-window scoring with exponential decay,
and status classification (ACTIVE / DORMANT / CLOSED).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    ActivityEventDB, ActivityStatusCurrent, UBIDMaster,
    UBIDSourceRecord, BusinessRecordDB, EventLedger,
    ActivityStatus, SignalClass
)
from backend.services.resolution.normalize import validate_pan, validate_gstin
from backend.services.resolution.registry import _write_ledger


# ─── Signal Weights ──────────────────────────────────────────────────────────

SIGNAL_WEIGHTS = {
    "STRONG_ACTIVE": 3.0,
    "WEAK_ACTIVE": 2.0,
    "NEUTRAL": 0.0,
    "DORMANCY": -2.0,
    "CLOSURE": -4.0,
}

# ─── Decay Parameters ───────────────────────────────────────────────────────

HALF_LIFE_DAYS = 180
LOOKBACK_DAYS = 548  # 18 months
STRONG_ACTIVE_RECENCY_DAYS = 180


def exponential_decay(age_days: float, half_life: float = HALF_LIFE_DAYS) -> float:
    """Compute exponential decay weight."""
    if age_days < 0:
        age_days = 0
    return math.exp(-math.log(2) * age_days / half_life)


# ─── Event Joining ───────────────────────────────────────────────────────────

def join_events_to_ubids(db: Session) -> dict:
    """Join unlinked activity events to UBIDs via PAN/GSTIN/record matching."""
    unlinked = db.query(ActivityEventDB).filter(ActivityEventDB.ubid.is_(None)).all()

    joined = 0
    unmatched = 0

    # Build lookup from source records → UBID
    source_to_ubid: dict[str, str] = {}
    for sr in db.query(UBIDSourceRecord).all():
        source_to_ubid[sr.record_id] = sr.ubid

    # Build gt_id → UBID mapping from source records
    gt_to_ubid: dict[str, str] = {}
    for sr in db.query(UBIDSourceRecord).all():
        rec = db.query(BusinessRecordDB).get(sr.record_id)
        if rec and rec.gt_id:
            gt_to_ubid[rec.gt_id] = sr.ubid

    for event in unlinked:
        # Try payload record_ref
        if event.payload and "record_ref" in event.payload:
            ref = event.payload["record_ref"]
            if ref in source_to_ubid:
                event.ubid = source_to_ubid[ref]
                event.joined_at = datetime.utcnow()
                joined += 1
                continue

        # Try gt_id from payload
        if event.payload and "business_gt_id" in event.payload:
            gt_id = event.payload["business_gt_id"]
            if gt_id in gt_to_ubid:
                event.ubid = gt_to_ubid[gt_id]
                event.joined_at = datetime.utcnow()
                joined += 1
                continue

        unmatched += 1

    db.commit()
    return {"joined": joined, "unmatched": unmatched}


# ─── Status Computation ─────────────────────────────────────────────────────

def compute_status_for_ubid(db: Session, ubid: str,
                            reference_date: Optional[date] = None) -> dict:
    """Compute activity status for a single UBID with full evidence."""
    if reference_date is None:
        reference_date = date.today()

    lookback_start = reference_date - timedelta(days=LOOKBACK_DAYS)

    events = db.query(ActivityEventDB).filter(
        ActivityEventDB.ubid == ubid,
        ActivityEventDB.event_date >= lookback_start,
        ActivityEventDB.event_date <= reference_date,
    ).order_by(ActivityEventDB.event_date.desc()).all()

    rolling_score = 0.0
    last_strong_active: Optional[date] = None
    has_closure = False
    timeline = []

    for event in events:
        age_days = (reference_date - event.event_date).days
        base_weight = SIGNAL_WEIGHTS.get(event.signal_class, 0.0)
        decay = exponential_decay(age_days)
        decayed_weight = base_weight * decay

        rolling_score += decayed_weight

        if event.signal_class == SignalClass.STRONG_ACTIVE.value:
            if last_strong_active is None or event.event_date > last_strong_active:
                last_strong_active = event.event_date

        if event.signal_class == SignalClass.CLOSURE.value:
            has_closure = True

        timeline.append({
            "event_id": event.id,
            "event_date": event.event_date.isoformat(),
            "source_system": event.source_system,
            "event_type": event.event_type,
            "signal_class": event.signal_class,
            "base_weight": base_weight,
            "age_days": age_days,
            "decay_factor": round(decay, 4),
            "decayed_weight": round(decayed_weight, 4),
            "is_tipping_point": False,
        })

    # Determine status
    status = _classify_status(rolling_score, last_strong_active, has_closure, reference_date)

    # Mark tipping point
    if timeline:
        cumulative = 0.0
        for entry in reversed(timeline):
            cumulative += entry["decayed_weight"]
            if status == ActivityStatus.ACTIVE.value and cumulative >= 2.0:
                entry["is_tipping_point"] = True
                break
            elif status == ActivityStatus.CLOSED.value and cumulative <= -3.0:
                entry["is_tipping_point"] = True
                break

    return {
        "ubid": ubid,
        "status": status,
        "rolling_score": round(rolling_score, 4),
        "last_strong_active_at": last_strong_active.isoformat() if last_strong_active else None,
        "event_count": len(events),
        "timeline": timeline,
    }


def _classify_status(rolling_score: float, last_strong_active: Optional[date],
                     has_closure: bool, reference_date: date) -> str:
    """Apply status classification rules."""
    # CLOSED: explicit closure event or very low score
    if has_closure or rolling_score <= -3.0:
        return ActivityStatus.CLOSED.value

    # ACTIVE: score ≥ +2 AND a strong-active event in last 6 months
    if rolling_score >= 2.0 and last_strong_active:
        days_since_strong = (reference_date - last_strong_active).days
        if days_since_strong <= STRONG_ACTIVE_RECENCY_DAYS:
            return ActivityStatus.ACTIVE.value

    # DORMANT: everything else
    return ActivityStatus.DORMANT.value


def run_activity_engine(db: Session) -> dict:
    """Run the full activity engine: join events then compute status for all UBIDs."""
    # Join events
    join_result = join_events_to_ubids(db)

    # Get all active UBIDs
    ubids = db.query(UBIDMaster).filter(UBIDMaster.status == "ACTIVE").all()

    stats = {"active": 0, "dormant": 0, "closed": 0, "processed": 0}

    for ubid_master in ubids:
        result = compute_status_for_ubid(db, ubid_master.ubid)

        # Upsert status
        existing = db.query(ActivityStatusCurrent).get(ubid_master.ubid)
        if existing:
            old_status = existing.status
            existing.status = result["status"]
            existing.score = result["rolling_score"]
            existing.last_strong_active_at = (
                datetime.fromisoformat(result["last_strong_active_at"])
                if result["last_strong_active_at"] else None
            )
            existing.event_count = result["event_count"]
            existing.last_recomputed_at = datetime.utcnow()
            existing.last_event_date = (
                date.fromisoformat(result["timeline"][0]["event_date"])
                if result["timeline"] else None
            )

            if old_status != result["status"]:
                existing.status_since = datetime.utcnow()
                _write_ledger(db, "STATUS_CHANGED", "STATUS", ubid_master.ubid, {
                    "old_status": old_status,
                    "new_status": result["status"],
                    "score": result["rolling_score"],
                })
        else:
            new_status = ActivityStatusCurrent(
                ubid=ubid_master.ubid,
                status=result["status"],
                score=result["rolling_score"],
                last_strong_active_at=(
                    datetime.fromisoformat(result["last_strong_active_at"])
                    if result["last_strong_active_at"] else None
                ),
                event_count=result["event_count"],
                status_since=datetime.utcnow(),
                last_recomputed_at=datetime.utcnow(),
                last_event_date=(
                    date.fromisoformat(result["timeline"][0]["event_date"])
                    if result["timeline"] else None
                ),
            )
            db.add(new_status)

        stats[result["status"].lower()] += 1
        stats["processed"] += 1

    db.commit()

    return {
        "join_result": join_result,
        "status_distribution": {k: v for k, v in stats.items() if k != "processed"},
        "total_processed": stats["processed"],
    }
