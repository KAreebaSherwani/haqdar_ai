"""Real reports store — the honest civic dataset.

Records ONLY four non-identifying fields per complaint:
reference_id, domain, district, date. Never the complaint text, never a name.

Storage backend is chosen automatically:
- If DATABASE_URL is set (Supabase / Postgres) -> use Postgres (persists across
  Render redeploys). This is the production path.
- Otherwise -> SQLite file (zero-config local development).

Either backend exposes the same three functions: record(), stats(), get_by_reference().
Nothing else in the app needs to know which one is active.
"""

import logging
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("haqdar.reports")

_lock = threading.Lock()
_DB_PATH: Path | None = None

# Detect backend once at import
_DATABASE_URL = (get_settings().database_url or "").strip()
_USE_PG = _DATABASE_URL.startswith("postgres")

# ---- Postgres (Supabase) backend -------------------------------------------
_pg_pool = None


def _pg():
    """Lazy psycopg connection pool (Supabase transaction pooler)."""
    global _pg_pool
    if _pg_pool is None:
        from psycopg_pool import ConnectionPool

        _pg_pool = ConnectionPool(_DATABASE_URL, min_size=1, max_size=4, open=True)
        with _pg_pool.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    reference_id TEXT,
                    domain TEXT NOT NULL,
                    district TEXT NOT NULL DEFAULT 'unspecified',
                    created_on DATE NOT NULL DEFAULT CURRENT_DATE
                )"""
            )
    return _pg_pool


# ---- SQLite backend (local dev) --------------------------------------------
def _db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path(get_settings().reports_db_path)
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def _sqlite():
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT,
            domain TEXT NOT NULL,
            district TEXT NOT NULL DEFAULT 'unspecified',
            created_on TEXT NOT NULL
        )"""
    )
    return conn


# ---- Public API ------------------------------------------------------------
def record(domain: str, district: str | None, reference_id: str | None = None) -> None:
    """Record one anonymous report. Never raises into the request path."""
    dom = domain or "general"
    dist = (district or "unspecified").strip() or "unspecified"
    ref = reference_id or ""
    try:
        if _USE_PG:
            with _pg().connection() as conn:
                conn.execute(
                    "INSERT INTO reports (reference_id, domain, district) VALUES (%s, %s, %s)",
                    (ref, dom, dist),
                )
        else:
            with _lock, _sqlite() as conn:
                conn.execute(
                    "INSERT INTO reports (reference_id, domain, district, created_on) "
                    "VALUES (?, ?, ?, ?)",
                    (ref, dom, dist, date.today().isoformat()),
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("report recording failed (non-fatal): %s", exc)


def stats() -> dict:
    """Real aggregates. Every number = a complaint actually processed."""
    try:
        if _USE_PG:
            return _stats_pg()
        return _stats_sqlite()
    except Exception as exc:  # noqa: BLE001
        logger.warning("stats read failed: %s", exc)
        return {"data_source": "real", "total_reports": 0, "this_month": 0,
                "top_issues": [], "districts": [], "daily_trend": []}


def _shape(total, this_month, top_issues, districts, trend) -> dict:
    return {
        "data_source": "real",
        "note": "Every number is a complaint actually processed by this system.",
        "total_reports": total,
        "this_month": this_month,
        "top_issues": top_issues,
        "districts": districts,
        "daily_trend": trend,
    }


def _stats_pg() -> dict:
    with _pg().connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        this_month = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE date_trunc('month', created_on) "
            "= date_trunc('month', CURRENT_DATE)"
        ).fetchone()[0]
        top_issues = [
            {"category": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT domain, COUNT(*) c FROM reports GROUP BY domain ORDER BY c DESC LIMIT 6"
            ).fetchall()
        ]
        districts = [
            {"name": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT district, COUNT(*) c FROM reports WHERE district <> 'unspecified' "
                "GROUP BY district ORDER BY c DESC LIMIT 10"
            ).fetchall()
        ]
        trend = []
        for i in range(5, -1, -1):
            d = (datetime.now() - timedelta(days=i)).date()
            n = conn.execute(
                "SELECT COUNT(*) FROM reports WHERE created_on = %s", (d,)
            ).fetchone()[0]
            trend.append({"date": d.isoformat(), "count": n})
    return _shape(total, this_month, top_issues, districts, trend)


def _stats_sqlite() -> dict:
    with _lock, _sqlite() as conn:
        total = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        month_start = date.today().replace(day=1).isoformat()
        this_month = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE created_on >= ?", (month_start,)
        ).fetchone()[0]
        top_issues = [
            {"category": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT domain, COUNT(*) c FROM reports GROUP BY domain ORDER BY c DESC LIMIT 6"
            )
        ]
        districts = [
            {"name": r[0], "count": r[1]}
            for r in conn.execute(
                "SELECT district, COUNT(*) c FROM reports WHERE district != 'unspecified' "
                "GROUP BY district ORDER BY c DESC LIMIT 10"
            )
        ]
        trend = []
        for i in range(5, -1, -1):
            d = (datetime.now() - timedelta(days=i)).date().isoformat()
            n = conn.execute(
                "SELECT COUNT(*) FROM reports WHERE created_on = ?", (d,)
            ).fetchone()[0]
            trend.append({"date": d, "count": n})
    return _shape(total, this_month, top_issues, districts, trend)


def get_by_reference(reference_id: str) -> dict | None:
    """Look up an anonymous report by its reference number (no personal data)."""
    try:
        if _USE_PG:
            with _pg().connection() as conn:
                row = conn.execute(
                    "SELECT reference_id, domain, district, created_on FROM reports "
                    "WHERE reference_id = %s LIMIT 1",
                    (reference_id,),
                ).fetchone()
        else:
            with _lock, _sqlite() as conn:
                row = conn.execute(
                    "SELECT reference_id, domain, district, created_on FROM reports "
                    "WHERE reference_id = ? LIMIT 1",
                    (reference_id,),
                ).fetchone()
        if not row:
            return None
        return {
            "reference_id": row[0],
            "domain": row[1],
            "district": row[2],
            "created_on": str(row[3]),
            "status": "Draft Generated",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("reference lookup failed: %s", exc)
        return None
