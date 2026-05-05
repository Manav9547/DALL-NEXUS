"""NexusID — Audit Tools: Recompute from Ledger & Active Learning.

recompute_from_ledger: Rebuilds system state purely from the event ledger.
active_learning: Retrains model from reviewer decisions.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    EventLedger, UBIDMaster, UBIDSourceRecord, MergeProvenance,
    ActivityStatusCurrent, CandidatePairDB, SessionLocal, init_db
)


def recompute_from_ledger(db: Session) -> dict:
    """Recompute system state from the event ledger alone.

    Replays all ledger events in order and builds:
    - Count of UBID creations
    - Count of merges (net of reversals)
    - Count of status changes
    - Count of review decisions

    Returns a comparison report.
    """
    entries = db.query(EventLedger).order_by(EventLedger.ledger_id).all()

    # Replay state
    ubids_created = set()
    merges = {}  # merge_id -> {winner, loser, reversed}
    status_changes = {}  # ubid -> latest_status
    reviews = 0

    for entry in entries:
        if entry.event_type == "UBID_CREATED":
            ubids_created.add(entry.aggregate_id)

        elif entry.event_type == "UBID_MERGED":
            merge_id = entry.aggregate_id
            merges[merge_id] = {
                "winner": entry.payload.get("winner"),
                "loser": entry.payload.get("loser"),
                "reversed": False,
            }

        elif entry.event_type == "MERGE_REVERSED":
            merge_id = entry.payload.get("merge_id")
            if merge_id in merges:
                merges[merge_id]["reversed"] = True

        elif entry.event_type == "STATUS_CHANGED":
            ubid = entry.aggregate_id
            status_changes[ubid] = entry.payload.get("new_status")

        elif entry.event_type == "REVIEW_DECIDED":
            reviews += 1

    # Net merges (excluding reversed)
    net_merges = sum(1 for m in merges.values() if not m["reversed"])

    # Compare with live state
    live_ubids = db.query(func.count(UBIDMaster.ubid)).scalar() or 0
    live_active_ubids = db.query(func.count(UBIDMaster.ubid)).filter(
        UBIDMaster.status == "ACTIVE").scalar() or 0
    live_merges = db.query(func.count(MergeProvenance.merge_id)).filter(
        MergeProvenance.reversed == False).scalar() or 0
    live_statuses = db.query(func.count(ActivityStatusCurrent.ubid)).scalar() or 0

    report = {
        "ledger_entries_replayed": len(entries),
        "recomputed": {
            "ubids_created": len(ubids_created),
            "net_merges": net_merges,
            "status_changes": len(status_changes),
            "reviews": reviews,
        },
        "live": {
            "total_ubids": live_ubids,
            "active_ubids": live_active_ubids,
            "net_merges": live_merges,
            "statuses_computed": live_statuses,
        },
        "parity_checks": {
            "merges_match": net_merges == live_merges,
        },
        "verified": True,
    }

    # Check parity
    if not report["parity_checks"]["merges_match"]:
        report["verified"] = False

    return report


def run_active_learning(db: Session) -> dict:
    """Active learning loop: retrain model from reviewer decisions.

    Pulls all reviewer decisions, augments training data, evaluates
    against holdout, and reports whether to promote the new model.
    """
    from backend.services.resolution.train_model import build_labelled_dataset, train_model

    # Get reviewer decisions
    reviewed = db.query(CandidatePairDB).filter(
        CandidatePairDB.review_status.in_(["CONFIRM", "REJECT"]),
        CandidatePairDB.reviewer_id.isnot(None),
    ).all()

    if len(reviewed) < 10:
        return {
            "status": "insufficient_data",
            "reviewed_pairs": len(reviewed),
            "message": "Need at least 10 reviewer decisions to retrain.",
        }

    # Build dataset (includes both ground-truth and reviewer labels)
    X, y, meta = build_labelled_dataset(db)

    if len(X) < 50:
        return {
            "status": "insufficient_data",
            "total_pairs": len(X),
            "message": "Need at least 50 labelled pairs to train.",
        }

    # Train new model
    metrics = train_model(X, y)

    # Check promotion criteria
    should_promote = (
        metrics["pr_auc"] >= 0.97 and
        metrics["false_merge_rate"] <= 0.01
    )

    return {
        "status": "promoted" if should_promote else "rolled_back",
        "reviewed_pairs": len(reviewed),
        "total_training_pairs": len(X),
        "new_model_metrics": {
            "pr_auc": metrics["pr_auc"],
            "roc_auc": metrics["roc_auc"],
            "precision_at_auto": metrics["precision_at_auto"],
            "false_merge_rate": metrics["false_merge_rate"],
        },
        "promotion_criteria": {
            "pr_auc >= 0.97": metrics["pr_auc"] >= 0.97,
            "false_merge_rate <= 0.01": metrics["false_merge_rate"] <= 0.01,
        },
        "should_promote": should_promote,
    }
