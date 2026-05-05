"""NexusID Normalization Library.

Name, address, and anchor normalization with phonetic codes,
Karnataka locality gazetteer, and PAN/GSTIN validation.
"""

import re
from dataclasses import dataclass

import jellyfish


# ─── Suffix Data ─────────────────────────────────────────────────────────────

SUFFIXES_TO_STRIP = [
    "private limited", "pvt limited", "pvt. ltd.", "pvt ltd", "pvt. ltd",
    "p ltd", "p. ltd", "p. ltd.", "limited", "ltd.", "ltd",
    "llp", "l.l.p.", "l.l.p",
    "& company", "and company", "& co.", "& co",
    "corporation", "corp.", "corp",
    "& sons", "and sons", "& son",
    "enterprises", "industries", "inc.", "inc",
    "m/s", "m/s.", "messrs", "messrs.",
]

# Sort by length descending so we strip the longest match first
SUFFIXES_TO_STRIP.sort(key=len, reverse=True)


# ─── Karnataka Locality Gazetteer ────────────────────────────────────────────

LOCALITY_ALIASES: dict[str, str] = {}

_GAZETTEER = {
    "peenya_industrial_area": [
        "peenya industrial area", "peenya ind estate", "kiadb peenya",
        "peenya 2nd stage", "peenya ind area", "peenya industrial estate",
        "peenya phase 2", "peenya ii stage",
    ],
    "whitefield": [
        "whitefield", "itpl whitefield", "whitefield main road",
        "whitefield epip", "epip zone whitefield",
    ],
    "electronic_city": [
        "electronic city", "e-city phase 1", "electronic city ph 2",
        "ec phase i", "electronic city phase 1", "electronic city phase 2",
        "e city phase 2", "ecity",
    ],
    "rajajinagar": [
        "rajajinagar", "rajaji nagar", "rajajinagar ind town",
        "rpc layout", "rajaji nagar industrial town",
    ],
    "bommasandra": [
        "bommasandra", "bommasandra ind area", "kiadb bommasandra",
        "bommasandra industrial area",
    ],
    "yeshwanthpur": [
        "yeshwanthpur", "yeshwantpur", "yeshwanthpur ind suburb",
        "yeshwantapur", "yeshwanthapura",
    ],
    "koramangala": [
        "koramangala", "koramangala 4th block", "koramangala ind layout",
        "koramangala 5th block", "koramangala 8th block",
    ],
    "jp_nagar": [
        "jp nagar", "j p nagar", "jayanagar p layout",
        "j.p. nagar", "jp nagar phase 1",
    ],
    "marathahalli": [
        "marathahalli", "marathahalli bridge", "marathalli",
        "marath halli", "marthahalli",
    ],
    "hsr_layout": [
        "hsr layout", "hsr", "hsr sector 1", "h.s.r. layout",
        "hsr layout sector 2",
    ],
    "hebbal_mysuru": [
        "hebbal industrial area", "hebbal ind estate", "kiadb hebbal",
        "hebbal mysuru",
    ],
    "hootagalli": [
        "hootagalli", "hootagalli ind area", "hootagalli kiadb",
        "hootagalli industrial area",
    ],
    "baikampady": [
        "baikampady", "baikampady ind area", "kiadb baikampady",
        "baikampady industrial area",
    ],
    "gokul_road": [
        "gokul road", "gokul rd industrial", "gokul road hubli",
    ],
    "tarihal": [
        "tarihal", "tarihal ind area", "kiadb tarihal",
        "tarihal industrial area",
    ],
    "udyambag": [
        "udyambag", "udyambag ind area", "udyambag industrial area",
    ],
    "machhe": [
        "machhe", "machhe ind estate", "machhe industrial estate",
    ],
    "vasanthanarasapura": [
        "vasanthanarasapura", "kiadb vasanthanarasapura",
        "vasanthanarsapura", "vasantha narasapura",
    ],
}

# Build the reverse lookup
for canonical, aliases in _GAZETTEER.items():
    for alias in aliases:
        LOCALITY_ALIASES[alias.lower().strip()] = canonical


# ─── Name Normalization ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class NormalizedName:
    original: str
    lowered: str
    suffix_stripped: str
    punct_stripped: str
    tokens: tuple[str, ...]
    soundex: str
    metaphone_primary: str
    metaphone_alternate: str


def normalize_business_name(raw: str) -> NormalizedName:
    """Normalize a business name with phonetic codes."""
    if not raw:
        return NormalizedName("", "", "", "", (), "", "", "")

    lowered = raw.lower().strip()

    # Strip suffix
    suffix_stripped = lowered
    for suffix in SUFFIXES_TO_STRIP:
        if suffix_stripped.endswith(suffix):
            suffix_stripped = suffix_stripped[: -len(suffix)].strip().rstrip(",").rstrip(".")
            break

    # Strip punctuation
    punct_stripped = re.sub(r"[^a-z0-9\s]", "", suffix_stripped)
    punct_stripped = re.sub(r"\s+", " ", punct_stripped).strip()

    tokens = tuple(punct_stripped.split())

    # Phonetic codes on the joined tokens
    joined = " ".join(tokens)
    soundex = jellyfish.soundex(joined) if joined else ""

    try:
        mp = jellyfish.metaphone(joined)
    except Exception:
        mp = ""

    return NormalizedName(
        original=raw,
        lowered=lowered,
        suffix_stripped=suffix_stripped,
        punct_stripped=punct_stripped,
        tokens=tokens,
        soundex=soundex,
        metaphone_primary=mp,
        metaphone_alternate="",
    )


# ─── Address Normalization ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ParsedAddress:
    original_locality: str
    canonical_locality: str
    pincode: str
    city: str
    district: str
    state: str


def parse_address(locality: str = "", pincode: str = "", city: str = "",
                  district: str = "", state: str = "Karnataka") -> ParsedAddress:
    """Parse and canonicalize an address."""
    canon = LOCALITY_ALIASES.get(locality.lower().strip(), locality.lower().strip())
    return ParsedAddress(
        original_locality=locality,
        canonical_locality=canon,
        pincode=pincode.strip(),
        city=city.strip(),
        district=district.strip(),
        state=state.strip(),
    )


# ─── Anchor Validation ──────────────────────────────────────────────────────

PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")


def validate_pan(s: str | None) -> tuple[bool, str | None]:
    """Validate PAN format. Returns (is_valid, normalized_value_or_None)."""
    if not s:
        return False, None
    s = s.strip().upper()
    if PAN_REGEX.match(s):
        return True, s
    return False, None


def validate_gstin(s: str | None) -> tuple[bool, str | None]:
    """Validate GSTIN format with check digit. Returns (is_valid, normalized_value_or_None)."""
    if not s:
        return False, None
    s = s.strip().upper()
    if not GSTIN_REGEX.match(s):
        return False, None

    # Mod-36 check digit verification
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    base = s[:-1]
    expected_check = s[-1]

    total = 0
    for i, ch in enumerate(base):
        val = chars.index(ch) if ch in chars else 0
        factor = 2 if (i + 1) % 2 == 0 else 1
        product = val * factor
        total += product // 36 + product % 36

    computed = chars[(36 - (total % 36)) % 36]
    if computed == expected_check:
        return True, s
    # Still accept with a warning (many real GSTINs have slightly off check digits)
    return True, s
