"""NexusID Synthetic Data Generator.

Generates realistic Karnataka business data across 5 department systems
with controlled corruptions, ground truth labels, and activity events.
"""

import hashlib
import json
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models import (
    BusinessRecordDB, ActivityEventDB, UBIDMaster, UBIDSourceRecord,
    ActivityStatusCurrent, AdapterHealthDB, EventLedger,
    init_db, SessionLocal, engine, Base
)

# ─── Constants ───────────────────────────────────────────────────────────────

SEED = 42
NUM_BUSINESSES = 800
YEARS = 3

NAME_PREFIXES = [
    "Apex", "Bharath", "Cauvery", "Deccan", "Eagle", "Fortune", "Global",
    "Hindustan", "Indian", "Jayalakshmi", "Krishna", "Lakshmi", "Mahesh",
    "Nandi", "Om", "Prasad", "Quality", "Royal", "Sri", "Triveni",
    "Unity", "Vidya", "Wipro", "Xcel", "Yashas", "Zenith", "Amba",
    "Basava", "Chamundi", "Dharma", "Ekta", "Ganga", "Hampi", "Indus",
    "Janata", "Kaveri", "Lotus", "Mysore", "Naveen", "Ojas", "Prabha",
    "Raman", "Sagar", "Tunga", "Uma", "Veda", "Wisteria", "Yashoda",
]

NAME_TYPES = [
    "Industries", "Enterprises", "Trading", "Solutions", "Tech",
    "Engineering", "Foods", "Textiles", "Pharma", "Constructions",
    "Motors", "Electronics", "Chemicals", "Steel", "Polymers",
    "Exports", "Imports", "Services", "Agro", "Power",
    "Logistics", "Infra", "Media", "Retail", "Healthcare",
]

SUFFIXES = [
    "Pvt Ltd", "Private Limited", "LLP", "Ltd", "& Co",
    "Enterprises", "Corporation", "", "& Sons", "Industries",
]

SUFFIX_VARIANTS = {
    "Pvt Ltd": ["Pvt. Ltd.", "Private Limited", "Pvt Ltd", "P Ltd", "PVT LTD"],
    "Private Limited": ["Pvt Ltd", "Pvt. Ltd.", "Private Ltd", "PRIVATE LIMITED"],
    "LLP": ["LLP", "L.L.P.", "llp"],
    "Ltd": ["Ltd", "Ltd.", "Limited", "LTD"],
    "& Co": ["& Co", "& Co.", "and Company", "& Company"],
    "& Sons": ["& Sons", "and Sons", "& Son"],
    "": [""],
}

DISTRICTS = {
    "Bengaluru Urban": {
        "localities": [
            ("Peenya Industrial Area", ["Peenya Ind Estate", "KIADB Peenya", "Peenya 2nd Stage"]),
            ("Whitefield", ["ITPL Whitefield", "Whitefield Main Road", "Whitefield EPIP"]),
            ("Electronic City", ["E-City Phase 1", "Electronic City Ph 2", "EC Phase I"]),
            ("Rajajinagar", ["Rajaji Nagar", "Rajajinagar Ind Town", "RPC Layout"]),
            ("Bommasandra", ["Bommasandra Ind Area", "KIADB Bommasandra"]),
            ("Yeshwanthpur", ["Yeshwantpur", "Yeshwanthpur Ind Suburb"]),
            ("Koramangala", ["Koramangala 4th Block", "Koramangala Ind Layout"]),
            ("JP Nagar", ["J P Nagar", "Jayanagar P Layout"]),
            ("Marathahalli", ["Marathahalli Bridge", "Marathalli"]),
            ("HSR Layout", ["HSR", "HSR Sector 1"]),
        ],
        "pincodes": ["560058", "560066", "560048", "560010", "560099", "560022", "560034", "560078", "560037", "560102"],
    },
    "Mysuru": {
        "localities": [
            ("Hebbal Industrial Area", ["Hebbal Ind Estate", "KIADB Hebbal"]),
            ("Hootagalli", ["Hootagalli Ind Area", "Hootagalli KIADB"]),
            ("Belagola", ["Belagola Ind Area"]),
        ],
        "pincodes": ["570016", "570018", "570020", "570023"],
    },
    "Mangaluru": {
        "localities": [
            ("Baikampady", ["Baikampady Ind Area", "KIADB Baikampady"]),
            ("Kulur", ["Kulur Ind Area"]),
            ("Surathkal", ["NITK Surathkal Area"]),
        ],
        "pincodes": ["575001", "575006", "575014", "575025"],
    },
    "Hubballi-Dharwad": {
        "localities": [
            ("Gokul Road", ["Gokul Rd Industrial"]),
            ("Tarihal", ["Tarihal Ind Area", "KIADB Tarihal"]),
        ],
        "pincodes": ["580020", "580025", "580030"],
    },
    "Belagavi": {
        "localities": [
            ("Udyambag", ["Udyambag Ind Area"]),
            ("Machhe", ["Machhe Ind Estate"]),
        ],
        "pincodes": ["590001", "590006", "590010", "590014"],
    },
    "Tumkur": {
        "localities": [
            ("Vasanthanarasapura", ["KIADB Vasanthanarasapura"]),
            ("Hirehalli", ["Hirehalli Ind Area"]),
        ],
        "pincodes": ["572101", "572103", "572106"],
    },
}

DEPARTMENTS = ["SHOP_EST", "FACTORIES", "LABOUR", "KSPCB", "GST"]

EVENT_TYPE_SIGNAL = {
    "LICENCE_RENEWAL": "STRONG_ACTIVE",
    "GST_FILING": "STRONG_ACTIVE",
    "TAX_PAYMENT": "STRONG_ACTIVE",
    "ANNUAL_RETURN": "STRONG_ACTIVE",
    "INSPECTION": "WEAK_ACTIVE",
    "POLLUTION_CLEARANCE": "WEAK_ACTIVE",
    "LABOUR_COMPLIANCE": "WEAK_ACTIVE",
    "COMPLIANCE_NOTICE": "NEUTRAL",
    "ELECTRICITY_DISCONNECT": "DORMANCY",
    "CLOSURE_CERT": "CLOSURE",
}


def generate_pan(rng: random.Random) -> str:
    """Generate a format-valid PAN: AAAAA9999A."""
    letters = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    digits = "".join(rng.choices("0123456789", k=4))
    check = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return f"{letters}{digits}{check}"


def generate_gstin(pan: str, state_code: str, rng: random.Random) -> str:
    """Generate a format-valid GSTIN from PAN."""
    entity = str(rng.randint(1, 9))
    base = f"{state_code}{pan}{entity}Z"
    # Simplified check digit (mod 36)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, ch in enumerate(base):
        val = chars.index(ch.upper()) if ch.upper() in chars else 0
        factor = (2 if (i + 1) % 2 == 0 else 1)
        product = val * factor
        total += product // 36 + product % 36
    check_digit = chars[(36 - (total % 36)) % 36]
    return base + check_digit


def corrupt_name(name: str, suffix: str, rng: random.Random) -> str:
    """Apply realistic corruptions to a business name."""
    corrupted = name
    roll = rng.random()

    if roll < 0.15:
        corrupted = corrupted.upper()
    elif roll < 0.30:
        corrupted = corrupted.lower()
    elif roll < 0.40:
        # Drop a character
        if len(corrupted) > 4:
            idx = rng.randint(1, len(corrupted) - 2)
            corrupted = corrupted[:idx] + corrupted[idx + 1:]
    elif roll < 0.50:
        # Add M/s prefix
        corrupted = "M/s " + corrupted
    elif roll < 0.55:
        # Swap two adjacent characters
        if len(corrupted) > 3:
            idx = rng.randint(1, len(corrupted) - 3)
            corrupted = corrupted[:idx] + corrupted[idx + 1] + corrupted[idx] + corrupted[idx + 2:]

    # Suffix variant
    if suffix and suffix in SUFFIX_VARIANTS:
        variants = SUFFIX_VARIANTS[suffix]
        new_suffix = rng.choice(variants)
        if rng.random() < 0.15:
            new_suffix = ""  # Drop suffix entirely
        corrupted = f"{corrupted} {new_suffix}".strip()
    elif suffix:
        corrupted = f"{corrupted} {suffix}"

    return corrupted


def corrupt_pincode(pincode: str, rng: random.Random) -> str:
    """5% chance of pincode typo."""
    if rng.random() < 0.05:
        idx = rng.randint(0, 5)
        chars = list(pincode)
        chars[idx] = str(rng.randint(0, 9))
        return "".join(chars)
    return pincode


def generate_phone(rng: random.Random) -> str:
    """Generate an Indian mobile number."""
    prefix = rng.choice(["98", "97", "96", "95", "94", "93", "91", "90", "88", "87", "86", "85"])
    rest = "".join([str(rng.randint(0, 9)) for _ in range(8)])
    return f"+91{prefix}{rest}"


def generate_email(name: str, rng: random.Random) -> str:
    """Generate a business email."""
    clean = name.lower().replace(" ", "").replace(".", "")[:15]
    domain = rng.choice(["gmail.com", "yahoo.co.in", "rediffmail.com", "outlook.com", f"{clean[:8]}.in"])
    return f"{clean}@{domain}"


def content_hash(record: dict) -> str:
    """Compute content hash for dedup."""
    data = json.dumps({
        "source_system": record.get("source_system", ""),
        "business_name": record.get("business_name", "").lower().strip(),
        "pincode": record.get("address_pincode", ""),
        "pan": record.get("pan"),
        "gstin": record.get("gstin"),
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def generate_all():
    """Generate the full synthetic dataset."""
    rng = random.Random(SEED)

    print("=" * 60)
    print("NexusID Synthetic Data Generator")
    print("=" * 60)
    print(f"Businesses: {NUM_BUSINESSES}")
    print(f"Departments: {len(DEPARTMENTS)}")
    print(f"Years of activity: {YEARS}")
    print()

    # Initialize DB
    Base.metadata.drop_all(engine)
    init_db()
    db = SessionLocal()

    businesses = []
    all_records = []
    all_events = []
    labels = []

    # ─── Generate Ground Truth Businesses ─────────────────────────────────
    print("[1/5] Generating ground truth businesses...")

    for i in range(NUM_BUSINESSES):
        gt_id = f"GT-{i:05d}"
        prefix = rng.choice(NAME_PREFIXES)
        btype = rng.choice(NAME_TYPES)
        suffix = rng.choice(SUFFIXES)
        name = f"{prefix} {btype}"

        district = rng.choice(list(DISTRICTS.keys()))
        dist_info = DISTRICTS[district]
        loc_name, loc_aliases = rng.choice(dist_info["localities"])
        pincode = rng.choice(dist_info["pincodes"])
        city = district.split("-")[0] if "-" in district else district

        has_pan = rng.random() < 0.60
        pan = generate_pan(rng) if has_pan else None
        has_gstin = rng.random() < 0.50 and pan is not None
        gstin = generate_gstin(pan, "29", rng) if has_gstin else None

        phone = generate_phone(rng)
        email = generate_email(name, rng)
        reg_date = date(
            rng.randint(2010, 2021),
            rng.randint(1, 12),
            rng.randint(1, 28)
        )

        # Ghost or closed status
        is_ghost = rng.random() < 0.12
        is_closed = rng.random() < 0.05 if not is_ghost else False

        business = {
            "gt_id": gt_id,
            "name": name,
            "suffix": suffix,
            "district": district,
            "locality": loc_name,
            "loc_aliases": loc_aliases,
            "pincode": pincode,
            "city": city,
            "pan": pan,
            "gstin": gstin,
            "phone": phone,
            "email": email,
            "reg_date": reg_date,
            "is_ghost": is_ghost,
            "is_closed": is_closed,
        }
        businesses.append(business)

    # ─── Generate Department Records ──────────────────────────────────────
    print("[2/5] Generating department records...")

    for biz in businesses:
        num_depts = rng.randint(2, min(6, len(DEPARTMENTS)))
        depts = rng.sample(DEPARTMENTS, num_depts)
        biz_records = []

        for dept in depts:
            # Main record
            record = _create_dept_record(biz, dept, rng)
            biz_records.append(record)
            all_records.append(record)

            # 8% chance of intra-department duplicate
            if rng.random() < 0.08:
                dup = _create_dept_record(biz, dept, rng, is_dup=True)
                biz_records.append(dup)
                all_records.append(dup)

        # Generate labels (all pairs within same gt_id = positive)
        for j in range(len(biz_records)):
            for k in range(j + 1, len(biz_records)):
                labels.append({
                    "record_a_id": biz_records[j]["id"],
                    "record_b_id": biz_records[k]["id"],
                    "is_match": True,
                    "gt_id": biz["gt_id"],
                })

    # ─── Store Records in DB ──────────────────────────────────────────────
    print(f"[3/5] Storing {len(all_records)} records in database...")

    for rec in all_records:
        db_rec = BusinessRecordDB(
            id=rec["id"],
            source_system=rec["source_system"],
            source_record_id=rec["source_record_id"],
            business_name=rec["business_name"],
            address_line=rec.get("address_line", ""),
            address_locality=rec.get("address_locality", ""),
            address_city=rec.get("address_city", ""),
            address_district=rec.get("address_district", ""),
            address_pincode=rec.get("address_pincode", ""),
            address_state="Karnataka",
            pan=rec.get("pan"),
            gstin=rec.get("gstin"),
            phone=rec.get("phone"),
            email=rec.get("email"),
            registration_date=rec.get("registration_date"),
            registration_type=rec.get("registration_type"),
            content_hash=content_hash(rec),
            gt_id=rec["gt_id"],
        )
        db.merge(db_rec)

    db.commit()

    # ─── Generate Activity Events ─────────────────────────────────────────
    print("[4/5] Generating activity events...")

    today = date.today()
    start_date = today - timedelta(days=YEARS * 365)

    for biz in businesses:
        gt_id = biz["gt_id"]
        # Find records for this business
        biz_record_ids = [r["id"] for r in all_records if r["gt_id"] == gt_id]
        if not biz_record_ids:
            continue

        if biz["is_closed"]:
            # Some activity then a closure
            num_events = rng.randint(3, 8)
            events = _generate_events(biz, biz_record_ids, start_date, today, num_events, rng)
            # Add closure event
            closure_date = today - timedelta(days=rng.randint(30, 365))
            closure = _make_event(biz, rng.choice(biz_record_ids), closure_date,
                                  "CLOSURE_CERT", "CLOSURE", rng)
            events.append(closure)
            all_events.extend(events)

        elif biz["is_ghost"]:
            # Activity that stopped 18+ months ago
            cutoff = today - timedelta(days=rng.randint(540, 900))
            num_events = rng.randint(3, 10)
            events = _generate_events(biz, biz_record_ids, start_date, cutoff, num_events, rng)
            all_events.extend(events)

        else:
            # Active business with ongoing events
            num_events = rng.randint(8, 25)
            events = _generate_events(biz, biz_record_ids, start_date, today, num_events, rng)
            all_events.extend(events)

    # Store events
    for evt in all_events:
        db_evt = ActivityEventDB(
            id=evt["id"],
            ubid=None,  # Will be joined later
            source_system=evt["source_system"],
            source_event_id=evt["source_event_id"],
            event_type=evt["event_type"],
            signal_class=evt["signal_class"],
            event_date=evt["event_date"],
            payload=evt.get("payload"),
            ingested_at=datetime.utcnow(),
        )
        db.merge(db_evt)

    db.commit()

    # ─── Initialize adapter health ────────────────────────────────────────
    for dept in DEPARTMENTS:
        dept_count = len([r for r in all_records if r["source_system"] == dept])
        health = AdapterHealthDB(
            source_system=dept,
            last_successful_pull_at=datetime.utcnow(),
            last_record_count=dept_count,
            total_records=dept_count,
            status="HEALTHY",
            freshness_seconds=rng.uniform(10, 300),
            updated_at=datetime.utcnow(),
        )
        db.merge(health)

    db.commit()

    # ─── Print Stats ──────────────────────────────────────────────────────
    print(f"[5/5] Generation complete!")
    print()
    print("─" * 40)
    print("Distribution Stats:")
    print(f"  Businesses:          {NUM_BUSINESSES}")
    print(f"  Total records:       {len(all_records)}")
    print(f"  Total events:        {len(all_events)}")
    print(f"  Positive label pairs:{len(labels)}")
    print()

    for dept in DEPARTMENTS:
        count = len([r for r in all_records if r["source_system"] == dept])
        print(f"  {dept:12s}: {count:5d} records")

    pan_count = len([b for b in businesses if b["pan"]])
    gstin_count = len([b for b in businesses if b["gstin"]])
    ghost_count = len([b for b in businesses if b["is_ghost"]])
    closed_count = len([b for b in businesses if b["is_closed"]])

    print()
    print(f"  PAN coverage:        {pan_count}/{NUM_BUSINESSES} ({100*pan_count/NUM_BUSINESSES:.1f}%)")
    print(f"  GSTIN coverage:      {gstin_count}/{NUM_BUSINESSES} ({100*gstin_count/NUM_BUSINESSES:.1f}%)")
    print(f"  Ghost businesses:    {ghost_count}/{NUM_BUSINESSES} ({100*ghost_count/NUM_BUSINESSES:.1f}%)")
    print(f"  Closed businesses:   {closed_count}/{NUM_BUSINESSES} ({100*closed_count/NUM_BUSINESSES:.1f}%)")
    print("─" * 40)

    db.close()
    return businesses, all_records, all_events, labels


def _create_dept_record(biz: dict, dept: str, rng: random.Random, is_dup: bool = False) -> dict:
    """Create a single corrupted department record from ground truth."""
    rec_id = str(uuid.uuid4())
    source_rec_id = f"{dept}-{uuid.uuid4().hex[:10].upper()}"

    name = corrupt_name(biz["name"], biz["suffix"], rng)
    locality = biz["locality"]
    if rng.random() < 0.30 and biz["loc_aliases"]:
        locality = rng.choice(biz["loc_aliases"])

    pincode = corrupt_pincode(biz["pincode"], rng)

    # Anchor sparsity: only 60% of dept records have anchors even when master has them
    pan = biz["pan"] if (biz["pan"] and rng.random() < 0.60) else None
    gstin = biz["gstin"] if (biz["gstin"] and rng.random() < 0.55) else None

    phone = biz["phone"] if rng.random() < 0.50 else None
    email = biz["email"] if rng.random() < 0.40 else None

    reg_date = biz["reg_date"]
    if rng.random() < 0.30:
        reg_date = reg_date + timedelta(days=rng.randint(-90, 180))

    return {
        "id": rec_id,
        "gt_id": biz["gt_id"],
        "source_system": dept,
        "source_record_id": source_rec_id,
        "business_name": name,
        "address_line": f"No. {rng.randint(1, 500)}, {rng.choice(['1st', '2nd', '3rd', '4th', '5th'])} Cross",
        "address_locality": locality,
        "address_city": biz["city"],
        "address_district": biz["district"],
        "address_pincode": pincode,
        "pan": pan,
        "gstin": gstin,
        "phone": phone,
        "email": email,
        "registration_date": reg_date,
        "registration_type": rng.choice(["NEW", "RENEWAL", "TRANSFER", "AMENDMENT"]),
    }


def _generate_events(biz: dict, record_ids: list, start: date, end: date,
                      count: int, rng: random.Random) -> list:
    """Generate activity events for a business."""
    events = []
    active_types = ["LICENCE_RENEWAL", "GST_FILING", "TAX_PAYMENT", "ANNUAL_RETURN",
                    "INSPECTION", "POLLUTION_CLEARANCE", "LABOUR_COMPLIANCE", "COMPLIANCE_NOTICE"]

    for _ in range(count):
        days_range = (end - start).days
        if days_range <= 0:
            days_range = 1
        evt_date = start + timedelta(days=rng.randint(0, days_range))
        evt_type = rng.choice(active_types)
        events.append(_make_event(biz, rng.choice(record_ids), evt_date, evt_type,
                                  EVENT_TYPE_SIGNAL[evt_type], rng))
    return events


def _make_event(biz: dict, record_id: str, evt_date: date,
                evt_type: str, signal: str, rng: random.Random) -> dict:
    """Create a single activity event."""
    dept = rng.choice(DEPARTMENTS)
    return {
        "id": str(uuid.uuid4()),
        "gt_id": biz["gt_id"],
        "source_system": dept,
        "source_event_id": f"EVT-{uuid.uuid4().hex[:10].upper()}",
        "event_type": evt_type,
        "signal_class": signal,
        "event_date": evt_date,
        "payload": {"business_gt_id": biz["gt_id"], "record_ref": record_id},
    }


if __name__ == "__main__":
    generate_all()
    print("\n✅ Synthetic data generated successfully!")
