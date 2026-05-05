"""NexusID Scoring Engine.

Five-feature scoring with weighted linear model and decision routing.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from backend.models import (
    BusinessRecordDB, CandidatePairDB, FeatureVector,
    DecisionType
)
from backend.services.resolution.normalize import (
    normalize_business_name, parse_address, validate_pan, validate_gstin
)


# ─── Model Weights (v1 weighted linear) ──────────────────────────────────────

WEIGHTS = {
    "anchor": 0.40,
    "name": 0.25,
    "address": 0.20,
    "contact": 0.10,
    "date": 0.05,
}

# ─── Thresholds ──────────────────────────────────────────────────────────────

AUTO_LINK_THRESHOLD = 0.88
REVIEW_THRESHOLD = 0.55
MODEL_VERSION = "weighted-linear-v1"


# ─── Feature Functions ───────────────────────────────────────────────────────

def compute_anchor_score(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> float:
    """1.0 if PAN or GSTIN exact-match, 0.0 otherwise."""
    valid_pan_a, pan_a = validate_pan(rec_a.pan)
    valid_pan_b, pan_b = validate_pan(rec_b.pan)
    if valid_pan_a and valid_pan_b and pan_a == pan_b:
        return 1.0

    valid_gst_a, gst_a = validate_gstin(rec_a.gstin)
    valid_gst_b, gst_b = validate_gstin(rec_b.gstin)
    if valid_gst_a and valid_gst_b and gst_a == gst_b:
        return 1.0

    # Anchor conflict: both have valid but different anchors → negative signal
    if valid_pan_a and valid_pan_b and pan_a != pan_b:
        return -0.5
    if valid_gst_a and valid_gst_b and gst_a != gst_b:
        return -0.5

    return 0.0


def compute_name_score(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> float:
    """Max of Jaro-Winkler and token-sort-ratio on suffix-stripped names."""
    norm_a = normalize_business_name(rec_a.business_name)
    norm_b = normalize_business_name(rec_b.business_name)

    if not norm_a.suffix_stripped or not norm_b.suffix_stripped:
        return 0.0

    jw = fuzz.jaro_winkler_similarity(norm_a.suffix_stripped, norm_b.suffix_stripped) / 100.0 \
        if hasattr(fuzz, 'jaro_winkler_similarity') else 0.0

    # Use rapidfuzz token_sort_ratio
    tsr = fuzz.token_sort_ratio(norm_a.suffix_stripped, norm_b.suffix_stripped) / 100.0

    return max(jw, tsr)


def compute_address_score(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> float:
    """Weighted combo: pincode exact + locality canonical match + token similarity."""
    addr_a = parse_address(rec_a.address_locality, rec_a.address_pincode,
                           rec_a.address_city, rec_a.address_district)
    addr_b = parse_address(rec_b.address_locality, rec_b.address_pincode,
                           rec_b.address_city, rec_b.address_district)

    score = 0.0

    # Pincode exact (0.4)
    if addr_a.pincode and addr_b.pincode and addr_a.pincode == addr_b.pincode:
        score += 0.4

    # Locality canonical match (0.3)
    if (addr_a.canonical_locality and addr_b.canonical_locality and
            addr_a.canonical_locality == addr_b.canonical_locality):
        score += 0.3
    elif addr_a.canonical_locality and addr_b.canonical_locality:
        loc_sim = fuzz.ratio(addr_a.canonical_locality, addr_b.canonical_locality) / 100.0
        score += 0.3 * loc_sim

    # District match (0.3)
    if addr_a.district and addr_b.district:
        if addr_a.district.lower() == addr_b.district.lower():
            score += 0.3
        else:
            dist_sim = fuzz.ratio(addr_a.district.lower(), addr_b.district.lower()) / 100.0
            score += 0.3 * dist_sim

    return min(score, 1.0)


def compute_contact_score(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> float:
    """Max of phone exact and email local-part match."""
    scores = []

    # Phone exact
    if rec_a.phone and rec_b.phone:
        phone_a = rec_a.phone.replace("+91", "").replace(" ", "").replace("-", "")[-10:]
        phone_b = rec_b.phone.replace("+91", "").replace(" ", "").replace("-", "")[-10:]
        if phone_a and phone_b and phone_a == phone_b:
            scores.append(1.0)

    # Email match
    if rec_a.email and rec_b.email:
        local_a = rec_a.email.split("@")[0].lower()
        local_b = rec_b.email.split("@")[0].lower()
        domain_a = rec_a.email.split("@")[-1].lower() if "@" in rec_a.email else ""
        domain_b = rec_b.email.split("@")[-1].lower() if "@" in rec_b.email else ""

        if local_a == local_b:
            scores.append(1.0 if domain_a == domain_b else 0.7)
        elif domain_a == domain_b and domain_a not in ("gmail.com", "yahoo.co.in", "outlook.com"):
            scores.append(0.5)

    return max(scores) if scores else 0.0


def compute_date_score(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> float:
    """1.0 if registration dates within 90 days, linear decay to 0 over 730 days."""
    if not rec_a.registration_date or not rec_b.registration_date:
        return 0.3  # Neutral when missing

    delta_days = abs((rec_a.registration_date - rec_b.registration_date).days)

    if delta_days <= 90:
        return 1.0
    elif delta_days >= 730:
        return 0.0
    else:
        return 1.0 - (delta_days - 90) / (730 - 90)


def compute_features(rec_a: BusinessRecordDB, rec_b: BusinessRecordDB) -> FeatureVector:
    """Compute the full feature vector for a candidate pair."""
    return FeatureVector(
        anchor_score=compute_anchor_score(rec_a, rec_b),
        name_score=compute_name_score(rec_a, rec_b),
        address_score=compute_address_score(rec_a, rec_b),
        contact_score=compute_contact_score(rec_a, rec_b),
        date_proximity_score=compute_date_score(rec_a, rec_b),
    )


def score_pair(features: FeatureVector) -> float:
    """Apply the weighted linear model to a feature vector."""
    raw = (
        WEIGHTS["anchor"] * features.anchor_score +
        WEIGHTS["name"] * features.name_score +
        WEIGHTS["address"] * features.address_score +
        WEIGHTS["contact"] * features.contact_score +
        WEIGHTS["date"] * features.date_proximity_score
    )
    return max(0.0, min(1.0, raw))


def route_decision(score: float, features: FeatureVector) -> str:
    """Route based on score and anchor-conflict check."""
    # Anchor conflict: different valid PAN/GSTIN → always HOLD
    if features.anchor_score < 0:
        return DecisionType.HOLD.value

    if score >= AUTO_LINK_THRESHOLD:
        return DecisionType.AUTO_LINK.value
    elif score >= REVIEW_THRESHOLD:
        return DecisionType.REVIEW.value
    else:
        return DecisionType.HOLD.value


def run_scoring(db: Session) -> dict:
    """Score all candidate pairs and route decisions."""
    pairs = db.query(CandidatePairDB).filter(CandidatePairDB.score.is_(None)).all()

    stats = {"scored": 0, "auto_link": 0, "review": 0, "hold": 0}
    record_cache: dict[str, BusinessRecordDB] = {}

    for pair in pairs:
        # Fetch records
        if pair.record_a_id not in record_cache:
            record_cache[pair.record_a_id] = db.query(BusinessRecordDB).get(pair.record_a_id)
        if pair.record_b_id not in record_cache:
            record_cache[pair.record_b_id] = db.query(BusinessRecordDB).get(pair.record_b_id)

        rec_a = record_cache[pair.record_a_id]
        rec_b = record_cache[pair.record_b_id]

        if not rec_a or not rec_b:
            continue

        features = compute_features(rec_a, rec_b)
        score = score_pair(features)
        decision = route_decision(score, features)

        pair.score = score
        pair.decision = decision
        pair.feature_breakdown = features.to_dict()
        pair.model_version = MODEL_VERSION
        pair.decided_at = datetime.utcnow()

        stats["scored"] += 1
        stats[decision.lower()] = stats.get(decision.lower(), 0) + 1

    db.commit()
    return stats
