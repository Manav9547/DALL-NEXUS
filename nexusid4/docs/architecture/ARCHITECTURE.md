# NexusID Architecture

## System Overview

NexusID is a five-layer system that transforms fragmented government records into a unified business identity graph with real-time activity inference.

### Layer 1: Ingestion

Read-only adapters pull from 5 department systems (Shop Establishment, Factories, Labour, KSPCB, GST). Each adapter speaks the department's native format and emits canonical `BusinessRecord` events. The adapter interface is **read-only by design** — there is no write method on the interface, enforced via static analysis.

**Key guarantee:** Source systems are never modified.

### Layer 2: Resolution

Three-strategy blocking engine reduces O(n²) comparisons to a tractable candidate set:

- **Anchor blocking** — groups by exact PAN or GSTIN match
- **Pincode + Soundex blocking** — groups by location + phonetic name code
- **Pincode + Name Prefix blocking** — groups by location + first 3 chars of normalized name

Each candidate pair is scored across five features (anchor match, name similarity via Jaro-Winkler + token sort, address match with locality gazetteer, contact match, registration date proximity), weighted, and routed:

- **Score ≥ 0.88** → Auto-link (conservative threshold; false-merge rate < 1%)
- **0.55 ≤ Score < 0.88** → Human review queue
- **Score < 0.55** → Hold separate

**Key guarantee:** A wrong merge is worse than a missed merge (asymmetric caution).

### Layer 3: UBID Registry

The identity graph stores Unified Business IDs in three formats:

- `UBID-PAN-ABCDE1234F` — anchored to PAN
- `UBID-GST-29ABCDE1234F1Z5` — anchored to GSTIN
- `UBID-INT-{hex}` — internal, no anchor yet

Every merge is reversible: the `merge_provenance` table records the full evidence chain, and `reverse_merge` restores the pre-merge state with a new ledger event.

**Key guarantee:** System state is a deterministic function of the event ledger.

### Layer 4: Activity Engine

Events from department systems (licence renewals, GST filings, inspections, compliance notices, closures) are joined to UBIDs and scored using an exponential-decay rolling window:

```
weight(event) = base_weight × exp(-ln(2) × age_days / 180)
```

Classification rules:
- **ACTIVE:** rolling_score ≥ +2 AND a strong-active event in the last 6 months
- **CLOSED:** explicit closure event OR rolling_score ≤ -3
- **DORMANT:** everything else

### Layer 5: Query & Audit

GraphQL-style query API enables analytical queries like the flagship:

> *"Find all active businesses in pincode 560058 that have not been inspected in the last 18 months"*

Every query, every merge, every reversal, every status change is written to an **immutable, hash-chained event ledger**. Chain integrity is verifiable via `POST /api/ledger/verify`.

## Data Flow

```
Department Systems (read-only)
         │
         ▼
    ┌─────────┐      ┌──────────┐      ┌─────────┐
    │ Adapters │ ───► │ Blocking │ ───► │ Scoring │
    └─────────┘      └──────────┘      └─────────┘
                                             │
                          ┌──────────────────┼──────────────────┐
                          ▼                  ▼                  ▼
                    ┌──────────┐      ┌───────────┐      ┌──────────┐
                    │ Auto-link│      │  Review   │      │   Hold   │
                    └─────┬────┘      │  Queue    │      └──────────┘
                          │           └───────────┘
                          ▼
                   ┌──────────────┐
                   │ UBID Registry│◄─── Reviewer Confirms
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ Activity     │
                   │ Engine       │
                   └──────┬───────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       ┌────────────┐         ┌──────────────┐
       │ Query API  │         │ Event Ledger │
       └────────────┘         │ (immutable)  │
                              └──────────────┘
```

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend API | FastAPI + SQLAlchemy | Async, typed, fast |
| Database | SQLite (dev) / PostgreSQL (prod) | Zero-config dev, production-grade prod |
| Frontend | React 18 + TypeScript + Tailwind | Type-safe, fast DX |
| Normalization | jellyfish + rapidfuzz | Industry-standard phonetic + fuzzy matching |
| Graph | NetworkX (in-memory) | Fast connected-component detection |
| Charts | Recharts | React-native, composable |
