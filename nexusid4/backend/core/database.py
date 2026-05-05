"""NexusID — Database Configuration.

Supports:
- PostgreSQL + TimescaleDB (production)
- SQLite (development/demo)

Configured via DATABASE_URL environment variable.
Defaults to SQLite if not set.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

# ─── Database URL ────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    _DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "nexusid.db")
    DATABASE_URL = f"sqlite:///{_DB_PATH}"

IS_POSTGRES = DATABASE_URL.startswith("postgresql")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ─── Engine Configuration ───────────────────────────────────────────────────

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
elif IS_POSTGRES:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ─── TimescaleDB Setup ──────────────────────────────────────────────────────

def setup_timescaledb():
    """Create TimescaleDB hypertables for time-series data.

    Only runs on PostgreSQL with TimescaleDB extension.
    """
    if not IS_POSTGRES:
        return {"mode": "sqlite", "hypertables": 0}

    try:
        with engine.connect() as conn:
            # Enable extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            conn.commit()

            # Convert activity_events to hypertable
            try:
                conn.execute(text(
                    "SELECT create_hypertable('activity_events', 'event_date', "
                    "if_not_exists => TRUE, migrate_data => TRUE)"
                ))
                conn.commit()
            except Exception:
                pass  # Already a hypertable or table doesn't exist yet

            return {"mode": "postgresql+timescaledb", "hypertables": 1}
    except Exception as e:
        return {"mode": "postgresql", "timescaledb_error": str(e)}


# ─── Event Ledger Protection ────────────────────────────────────────────────

def setup_ledger_protection():
    """Create a database trigger that rejects UPDATE and DELETE on event_ledger.

    On PostgreSQL: creates a real trigger function.
    On SQLite: uses application-level enforcement (no trigger support for this).
    """
    if not IS_POSTGRES:
        return {"mode": "sqlite", "trigger": "application-level"}

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION prevent_ledger_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'event_ledger is immutable: UPDATE and DELETE are forbidden';
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """))

            conn.execute(text("""
                DROP TRIGGER IF EXISTS no_update_ledger ON event_ledger;
                CREATE TRIGGER no_update_ledger
                    BEFORE UPDATE OR DELETE ON event_ledger
                    FOR EACH ROW
                    EXECUTE FUNCTION prevent_ledger_mutation();
            """))

            conn.commit()
            return {"mode": "postgresql", "trigger": "database-level"}
    except Exception as e:
        return {"mode": "postgresql", "trigger_error": str(e)}


# ─── Health Check ────────────────────────────────────────────────────────────

def check_database_health() -> dict:
    """Check database connectivity and basic health."""
    try:
        with engine.connect() as conn:
            if IS_POSTGRES:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                return {
                    "status": "healthy",
                    "engine": "postgresql",
                    "version": version,
                    "pool_size": engine.pool.size(),
                    "pool_checked_out": engine.pool.checkedout(),
                }
            else:
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                return {
                    "status": "healthy",
                    "engine": "sqlite",
                    "version": version,
                }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def get_db_info() -> dict:
    """Get database configuration info."""
    return {
        "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "is_postgres": IS_POSTGRES,
        "is_sqlite": IS_SQLITE,
        "pool_size": getattr(engine.pool, '_pool', None) and engine.pool.size() if IS_POSTGRES else None,
    }
