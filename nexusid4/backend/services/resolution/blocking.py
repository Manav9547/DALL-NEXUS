"""NexusID Blocking Engine.

Three-strategy blocking engine that reduces O(n²) to tractable candidate pairs
while maintaining ≥99% recall on true matches.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Iterator

from sqlalchemy.orm import Session

from backend.models import BusinessRecordDB, CandidatePairDB
from backend.services.resolution.normalize import (
    normalize_business_name, parse_address, validate_pan, validate_gstin
)


def run_blocking(db: Session) -> dict:
    """Run all three blocking strategies and store deduplicated candidate pairs.

    Returns statistics about the blocking run.
    """
    records = db.query(BusinessRecordDB).all()
    if len(records) < 2:
        return {"total_records": len(records), "total_pairs": 0, "strategies": {}}

    # Build lookup
    record_map = {r.id: r for r in records}
    seen_pairs: set[tuple[str, str]] = set()
    pairs_by_strategy: dict[str, int] = defaultdict(int)
    all_pairs: list[CandidatePairDB] = []

    # ─── Strategy 1: Anchor Blocking (exact PAN or GSTIN) ─────────────────
    pan_groups: dict[str, list[str]] = defaultdict(list)
    gstin_groups: dict[str, list[str]] = defaultdict(list)

    for r in records:
        valid_pan, norm_pan = validate_pan(r.pan)
        if valid_pan and norm_pan:
            pan_groups[norm_pan].append(r.id)

        valid_gstin, norm_gstin = validate_gstin(r.gstin)
        if valid_gstin and norm_gstin:
            gstin_groups[norm_gstin].append(r.id)

    for group in list(pan_groups.values()) + list(gstin_groups.values()):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pair = _ordered(group[i], group[j])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pairs_by_strategy["ANCHOR"] += 1
                    all_pairs.append(_make_pair(pair, ["ANCHOR"]))

    # ─── Strategy 2: Pincode + Soundex Blocking ──────────────────────────
    ps_groups: dict[str, list[str]] = defaultdict(list)

    for r in records:
        if r.address_pincode:
            norm = normalize_business_name(r.business_name)
            if norm.soundex:
                key = f"{r.address_pincode}:{norm.soundex}"
                ps_groups[key].append(r.id)

    for group in ps_groups.values():
        if len(group) > 50:
            continue  # Skip over-broad groups
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pair = _ordered(group[i], group[j])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pairs_by_strategy["PINCODE_SOUNDEX"] += 1
                    all_pairs.append(_make_pair(pair, ["PINCODE_SOUNDEX"]))

    # ─── Strategy 3: Pincode + Name Prefix Blocking ──────────────────────
    pp_groups: dict[str, list[str]] = defaultdict(list)

    for r in records:
        if r.address_pincode:
            norm = normalize_business_name(r.business_name)
            if len(norm.punct_stripped) >= 3:
                key = f"{r.address_pincode}:{norm.punct_stripped[:3]}"
                pp_groups[key].append(r.id)

    for group in pp_groups.values():
        if len(group) > 50:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pair = _ordered(group[i], group[j])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    pairs_by_strategy["PINCODE_PREFIX"] += 1
                    all_pairs.append(_make_pair(pair, ["PINCODE_PREFIX"]))

    # ─── Store to DB ─────────────────────────────────────────────────────
    # Clear existing pairs
    db.query(CandidatePairDB).delete()

    for pair_db in all_pairs:
        db.add(pair_db)

    db.commit()

    n = len(records)
    n_squared = n * (n - 1) // 2

    return {
        "total_records": n,
        "total_pairs": len(all_pairs),
        "n_squared": n_squared,
        "reduction_ratio": f"{100 * len(all_pairs) / max(n_squared, 1):.4f}%",
        "strategies": dict(pairs_by_strategy),
    }


def _ordered(a: str, b: str) -> tuple[str, str]:
    """Canonical pair ordering."""
    return (a, b) if a < b else (b, a)


def _make_pair(pair: tuple[str, str], keys: list[str]) -> CandidatePairDB:
    """Create a CandidatePairDB from an ordered pair."""
    return CandidatePairDB(
        id=str(uuid.uuid4()),
        record_a_id=pair[0],
        record_b_id=pair[1],
        blocking_keys=keys,
        created_at=datetime.utcnow(),
    )
