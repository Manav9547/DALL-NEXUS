"""NexusID — PII Sanitizer & Explanation Generator.

Scrambles all PII fields before sending to any LLM.
The mapping from real → scrambled is held in-memory and never persisted.
"""

from __future__ import annotations

import hashlib
import random
import string
from typing import Optional

# ─── Scramble Functions ──────────────────────────────────────────────────────

_FAKE_NAMES = [
    "Alpha Corp", "Beta Industries", "Gamma Solutions", "Delta Trading",
    "Epsilon Tech", "Zeta Enterprises", "Eta Services", "Theta Exports",
    "Iota Engineering", "Kappa Logistics", "Lambda Systems", "Mu Industries",
]

_FAKE_LOCALITIES = [
    "Industrial Zone A", "Commerce Park B", "Trade Center C",
    "Business Hub D", "Enterprise Area E", "Industrial Sector F",
]


def _scramble_name(name: str, seed: int) -> str:
    rng = random.Random(seed)
    return rng.choice(_FAKE_NAMES)


def _scramble_address(locality: str, seed: int) -> str:
    rng = random.Random(seed)
    return rng.choice(_FAKE_LOCALITIES)


def _mask_pan(pan: Optional[str]) -> Optional[str]:
    if not pan or len(pan) < 5:
        return None
    return f"XXX{pan[3:5]}XXXX{pan[-1] if len(pan) >= 10 else 'X'}"


def _mask_gstin(gstin: Optional[str]) -> Optional[str]:
    if not gstin or len(gstin) < 6:
        return None
    return f"XX{gstin[2:4]}XXXXXXXXXXX"


def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    return "+91XXXXXXXX" + phone[-2:] if len(phone) >= 4 else "XXXX"


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{'x' * min(len(local), 8)}@{domain}"


# ─── Sanitizer ───────────────────────────────────────────────────────────────

def sanitize_record(record: dict, seed: Optional[int] = None) -> dict:
    """Sanitize a record dict, replacing all PII with scrambled values.

    The seed ensures the same record always maps to the same scrambled output
    within a session, for consistency in explanations.
    """
    if seed is None:
        seed = hash(record.get("id", "")) % (2**31)

    return {
        "id": record.get("id"),
        "source_system": record.get("source_system"),
        "source_record_id": f"SRC-{hashlib.md5(str(record.get('source_record_id', '')).encode()).hexdigest()[:8].upper()}",
        "business_name": _scramble_name(record.get("business_name", ""), seed),
        "normalized_name": _scramble_name(record.get("normalized_name", ""), seed + 1),
        "address_locality": _scramble_address(record.get("address_locality", ""), seed),
        "address_pincode": record.get("address_pincode"),  # Pincode is non-PII
        "address_city": record.get("address_city"),  # City is non-PII
        "address_district": record.get("address_district"),  # District is non-PII
        "pan": _mask_pan(record.get("pan")),
        "gstin": _mask_gstin(record.get("gstin")),
        "phone": _mask_phone(record.get("phone")),
        "email": _mask_email(record.get("email")),
        "registration_date": record.get("registration_date"),
    }


def sanitize_pair_for_llm(record_a: dict, record_b: dict,
                          features: dict) -> dict:
    """Sanitize a candidate pair for LLM consumption.

    Returns the sanitized payload that would be sent to the LLM.
    NO raw PII is included.
    """
    seed_a = hash(record_a.get("id", "a")) % (2**31)
    seed_b = hash(record_b.get("id", "b")) % (2**31)

    return {
        "record_a": sanitize_record(record_a, seed_a),
        "record_b": sanitize_record(record_b, seed_b),
        "features": features,
        "note": "All business names, addresses, phone numbers, and emails have been scrambled. PAN/GSTIN are masked. This data is safe for LLM processing.",
    }


def verify_no_pii(payload: dict, original_records: list[dict]) -> dict:
    """Verify that a sanitized payload contains zero raw PII from the originals.

    Returns a verification report.
    """
    violations = []
    payload_str = str(payload).lower()

    for rec in original_records:
        # Check business name
        name = rec.get("business_name", "")
        if name and len(name) > 3 and name.lower() in payload_str:
            violations.append(f"Raw business name found: {name[:20]}...")

        # Check phone
        phone = rec.get("phone", "")
        if phone and len(phone) > 6:
            clean_phone = phone.replace("+91", "").replace(" ", "").replace("-", "")
            if clean_phone in payload_str:
                violations.append(f"Raw phone found: {phone}")

        # Check email
        email = rec.get("email", "")
        if email and "@" in email:
            local = email.split("@")[0]
            if len(local) > 3 and local.lower() in payload_str:
                violations.append(f"Raw email local part found: {email}")

        # Check PAN (full, unmasked)
        pan = rec.get("pan", "")
        if pan and len(pan) == 10 and pan in str(payload):
            violations.append(f"Raw PAN found: {pan}")

        # Check GSTIN (full, unmasked)
        gstin = rec.get("gstin", "")
        if gstin and len(gstin) == 15 and gstin in str(payload):
            violations.append(f"Raw GSTIN found: {gstin}")

    return {
        "verified": len(violations) == 0,
        "violations": violations,
        "fields_checked": ["business_name", "phone", "email", "pan", "gstin"],
    }


# ─── Explanation Generator ───────────────────────────────────────────────────

def generate_explanation(features: dict, score: float, decision: str) -> str:
    """Generate a plain-English explanation of the score breakdown.

    Uses only the feature values (no PII). In production, this could call
    an LLM on the sanitized data for richer explanations.
    """
    parts = []

    anchor = features.get("anchor_score", 0)
    name = features.get("name_score", 0)
    address = features.get("address_score", 0)
    contact = features.get("contact_score", 0)
    date = features.get("date_proximity_score", 0)

    # Anchor
    if anchor >= 1.0:
        parts.append("These records share an exact PAN or GSTIN match, which is the strongest signal of identity equivalence.")
    elif anchor < 0:
        parts.append("WARNING: These records have conflicting anchors (different valid PAN or GSTIN), which is a strong signal they are different businesses.")
    elif anchor == 0:
        parts.append("Neither record has a matching anchor identifier (PAN/GSTIN), so the match depends entirely on other features.")

    # Name
    if name >= 0.9:
        parts.append(f"The business names are highly similar (score: {name:.0%}), suggesting they refer to the same entity with minor spelling or formatting differences.")
    elif name >= 0.7:
        parts.append(f"The business names show moderate similarity (score: {name:.0%}). Differences may include suffix variations (Pvt Ltd vs Private Limited), abbreviations, or transliteration.")
    elif name >= 0.4:
        parts.append(f"The business names have limited similarity (score: {name:.0%}), which could indicate a legitimate match with significant name changes, or two different businesses.")
    else:
        parts.append(f"The business names are quite different (score: {name:.0%}), which reduces confidence in a match.")

    # Address
    if address >= 0.8:
        parts.append(f"The addresses are a strong match (score: {address:.0%}), with matching pincode and locality.")
    elif address >= 0.5:
        parts.append(f"The addresses partially match (score: {address:.0%}). The pincode or locality may differ slightly.")
    else:
        parts.append(f"The addresses show limited similarity (score: {address:.0%}).")

    # Contact
    if contact >= 0.8:
        parts.append("Contact information (phone or email) matches, adding confidence to the identity link.")
    elif contact > 0:
        parts.append(f"Partial contact match detected (score: {contact:.0%}).")

    # Date
    if date >= 0.8:
        parts.append("Registration dates are close together, consistent with the same business registering across departments in a similar timeframe.")

    # Verdict
    parts.append("")
    if decision == "AUTO_LINK":
        parts.append(f"RECOMMENDATION: Auto-link (score: {score:.0%}). The evidence strongly supports these being the same business.")
    elif decision == "REVIEW":
        parts.append(f"RECOMMENDATION: Human review required (score: {score:.0%}). The evidence is suggestive but not conclusive.")
    else:
        parts.append(f"RECOMMENDATION: Hold separate (score: {score:.0%}). Insufficient evidence for a match.")

    return " ".join(parts)
