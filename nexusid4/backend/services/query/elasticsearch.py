"""NexusID — ElasticSearch Integration Layer.

Provides full-text search with:
- Edge n-gram analyzer for typo-tolerant name search
- Soundex analyzer for phonetic matching
- Structured filtering by pincode, district, status
- SQL LIKE fallback when ES is not available

Index: businesses-v1
"""

from __future__ import annotations

import os
import time
from typing import Optional

# ─── Configuration ───────────────────────────────────────────────────────────

ES_URL = os.getenv("ELASTICSEARCH_URL", "")
ES_ENABLED = bool(ES_URL)
INDEX_NAME = "businesses-v1"

_es_client = None


def get_es():
    """Get ElasticSearch client, or None."""
    global _es_client
    if not ES_ENABLED:
        return None
    if _es_client is None:
        try:
            from elasticsearch import Elasticsearch
            _es_client = Elasticsearch(ES_URL)
            _es_client.info()
        except Exception:
            _es_client = None
    return _es_client


# ─── Index Schema ────────────────────────────────────────────────────────────

INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "edge_ngram_analyzer": {
                    "type": "custom",
                    "tokenizer": "edge_ngram_tokenizer",
                    "filter": ["lowercase"],
                },
                "soundex_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "soundex_filter"],
                },
                "kannada_translit": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "icu_folding"],
                },
            },
            "tokenizer": {
                "edge_ngram_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 15,
                    "token_chars": ["letter", "digit"],
                },
            },
            "filter": {
                "soundex_filter": {
                    "type": "phonetic",
                    "encoder": "soundex",
                    "replace": False,
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "ubid": {"type": "keyword"},
            "primary_name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "edge_ngram": {"type": "text", "analyzer": "edge_ngram_analyzer"},
                    "soundex": {"type": "text", "analyzer": "soundex_analyzer"},
                },
            },
            "name_variants": {"type": "text", "analyzer": "standard"},
            "anchor_type": {"type": "keyword"},
            "anchor_value": {"type": "keyword"},
            "address_locality": {"type": "text"},
            "address_pincode": {"type": "keyword"},
            "address_district": {"type": "keyword"},
            "address_city": {"type": "keyword"},
            "status": {"type": "keyword"},
            "activity_score": {"type": "float"},
            "last_strong_active_at": {"type": "date"},
            "source_record_count": {"type": "integer"},
            "created_at": {"type": "date"},
        }
    },
}


# ─── Index Management ───────────────────────────────────────────────────────

def create_index() -> dict:
    """Create the businesses index with analyzers. Idempotent."""
    es = get_es()
    if not es:
        return {"mode": "fallback", "reason": "ElasticSearch not available"}

    try:
        if not es.indices.exists(index=INDEX_NAME):
            es.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
            return {"mode": "elasticsearch", "created": True}
        return {"mode": "elasticsearch", "created": False, "exists": True}
    except Exception as e:
        return {"mode": "elasticsearch", "error": str(e)}


def reindex_all(db) -> dict:
    """Full reindex from database to ElasticSearch."""
    from backend.models import UBIDMaster, UBIDSourceRecord, ActivityStatusCurrent, BusinessRecordDB
    from sqlalchemy import func

    es = get_es()
    if not es:
        return {"mode": "fallback", "indexed": 0}

    create_index()

    ubids = db.query(UBIDMaster).filter(UBIDMaster.status == "ACTIVE").all()
    indexed = 0

    for ubid in ubids:
        act = db.query(ActivityStatusCurrent).get(ubid.ubid)
        src_count = db.query(func.count(UBIDSourceRecord.id)).filter(
            UBIDSourceRecord.ubid == ubid.ubid).scalar() or 0

        # Collect name variants from source records
        variants = []
        srs = db.query(UBIDSourceRecord).filter(UBIDSourceRecord.ubid == ubid.ubid).all()
        for sr in srs:
            rec = db.query(BusinessRecordDB).get(sr.record_id)
            if rec and rec.business_name not in variants:
                variants.append(rec.business_name)

        doc = {
            "ubid": ubid.ubid,
            "primary_name": ubid.primary_name or "",
            "name_variants": variants,
            "anchor_type": ubid.anchor_type,
            "anchor_value": ubid.anchor_value,
            "address_locality": "",
            "address_pincode": ubid.primary_pincode or "",
            "address_district": ubid.primary_district or "",
            "address_city": "",
            "status": act.status if act else "UNKNOWN",
            "activity_score": act.score if act else 0,
            "source_record_count": src_count,
            "created_at": ubid.created_at.isoformat() if ubid.created_at else None,
        }

        try:
            es.index(index=INDEX_NAME, id=ubid.ubid, body=doc)
            indexed += 1
        except Exception:
            pass

    return {"mode": "elasticsearch", "indexed": indexed, "total": len(ubids)}


# ─── Search ──────────────────────────────────────────────────────────────────

def search_businesses(
    query: str = "",
    status: Optional[str] = None,
    district: Optional[str] = None,
    pincode: Optional[str] = None,
    limit: int = 20,
    db=None,
) -> dict:
    """Search for businesses using ES or SQL fallback.

    ES search uses multi-field matching:
    - Standard text match on primary_name (exact tokens)
    - Edge n-gram match (typo-tolerant: "Aypex" finds "Apex")
    - Soundex match (phonetic: "Aypex Textyle" finds "Apex Textiles")
    """
    es = get_es()
    start = time.time()

    if es and query:
        return _search_es(es, query, status, district, pincode, limit, start)
    elif db:
        return _search_sql(db, query, status, district, pincode, limit, start)
    else:
        return {"items": [], "total": 0, "mode": "none", "latency_ms": 0}


def _search_es(es, query: str, status, district, pincode, limit, start) -> dict:
    """ElasticSearch multi-field search with fuzzy matching."""
    must = []
    filter_clauses = []

    if query:
        must.append({
            "multi_match": {
                "query": query,
                "fields": [
                    "primary_name^3",
                    "primary_name.edge_ngram^2",
                    "primary_name.soundex^1",
                    "name_variants^1.5",
                    "anchor_value^5",
                    "address_pincode^2",
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })

    if status:
        filter_clauses.append({"term": {"status": status}})
    if district:
        filter_clauses.append({"term": {"address_district": district}})
    if pincode:
        filter_clauses.append({"term": {"address_pincode": pincode}})

    body = {
        "query": {
            "bool": {
                "must": must or [{"match_all": {}}],
                "filter": filter_clauses,
            }
        },
        "size": limit,
    }

    try:
        result = es.search(index=INDEX_NAME, body=body)
        hits = result.get("hits", {}).get("hits", [])
        items = [
            {**h["_source"], "es_score": h.get("_score", 0)}
            for h in hits
        ]
        elapsed_ms = (time.time() - start) * 1000

        return {
            "items": items,
            "total": result.get("hits", {}).get("total", {}).get("value", len(items)),
            "mode": "elasticsearch",
            "latency_ms": round(elapsed_ms, 2),
        }
    except Exception as e:
        return {"items": [], "total": 0, "mode": "elasticsearch", "error": str(e)}


def _search_sql(db, query: str, status, district, pincode, limit, start) -> dict:
    """SQL LIKE fallback search."""
    from backend.models import UBIDMaster, ActivityStatusCurrent, UBIDSourceRecord
    from sqlalchemy import func

    q = db.query(UBIDMaster).filter(UBIDMaster.status == "ACTIVE")

    if query:
        q_upper = query.upper().strip()
        if q_upper.startswith("UBID-"):
            q = q.filter(UBIDMaster.ubid == q_upper)
        elif len(q_upper) == 10 and q_upper[:5].isalpha():
            q = q.filter(UBIDMaster.anchor_value == q_upper)
        elif len(q_upper) == 15:
            q = q.filter(UBIDMaster.anchor_value == q_upper)
        elif len(query.strip()) == 6 and query.strip().isdigit():
            q = q.filter(UBIDMaster.primary_pincode == query.strip())
        else:
            q = q.filter(UBIDMaster.primary_name.ilike(f"%{query}%"))

    if district:
        q = q.filter(UBIDMaster.primary_district.ilike(f"%{district}%"))

    if status:
        status_ubids = db.query(ActivityStatusCurrent.ubid).filter(
            ActivityStatusCurrent.status == status).subquery()
        q = q.filter(UBIDMaster.ubid.in_(status_ubids))

    results = q.limit(limit).all()
    items = []
    for ubid in results:
        src_count = db.query(func.count(UBIDSourceRecord.id)).filter(
            UBIDSourceRecord.ubid == ubid.ubid).scalar() or 0
        act = db.query(ActivityStatusCurrent).get(ubid.ubid)
        items.append({
            "ubid": ubid.ubid,
            "primary_name": ubid.primary_name,
            "anchor_type": ubid.anchor_type,
            "anchor_value": ubid.anchor_value,
            "address_pincode": ubid.primary_pincode,
            "address_district": ubid.primary_district,
            "status": act.status if act else "UNKNOWN",
            "activity_score": act.score if act else 0,
            "source_record_count": src_count,
        })

    elapsed_ms = (time.time() - start) * 1000
    return {"items": items, "total": len(items), "mode": "sql-fallback", "latency_ms": round(elapsed_ms, 2)}
