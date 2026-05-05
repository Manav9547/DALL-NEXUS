# NexusID

**A real-time business identity resolution and activity-inference system for Karnataka's regulatory ecosystem.**

[![CI](https://img.shields.io/badge/build-passing-brightgreen)]() [![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)]() [![License](https://img.shields.io/badge/license-MIT-blue)]()

## The Problem

Karnataka's 40+ regulatory departments each maintain independent business registries with no shared identifier. The same business exists as 4–8 different records — different names, different addresses, different (or missing) anchors. The State cannot reliably answer: *"Who is operating, where, in what sector, and are they still open?"*

## The Solution

NexusID assigns a stable **Unified Business ID (UBID)** to every business by resolving heterogeneous records into a single identity graph, then continuously infers operating status (Active / Dormant / Closed) from regulatory event streams. Department source systems are **read-only** — NexusID never writes to them.

## Quickstart

```bash
cd nexusid
pip install -r backend/requirements.txt
python tools/synthetic_data/generate.py
python backend/main.py &
cd frontend && npm install && npm run dev
```

## Architecture

See [ARCHITECTURE.md](./docs/architecture/ARCHITECTURE.md) for full details.

```
Source Systems → Adapters → Normalisation → Blocking → Scoring → UBID Registry
                                                                       ↓
Activity Events → Joiner → Decay Scorer → Status Store → Query API → UI
                                                                       ↓
                                                              Event Ledger (immutable)
```
