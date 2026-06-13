"""Seed the REPORTS table (Supabase/Postgres or local SQLite) with realistic
mock complaints so the demo stats, charts, and heatmap look active.

IMPORTANT: this only touches the reports storage room (Supabase/SQLite).
It NEVER touches the vector store (Chroma) — the AI's verified law brain stays
clean and unpoisoned. Laws and reports live in two separate rooms by design.

Run once, locally or against Supabase:
    python -m app.scripts.seed_reports            # default ~80 rows
    python -m app.scripts.seed_reports 150        # custom count

Honesty note for the demo: these are clearly seed/representative records.
If asked, say "we pre-loaded representative historical data; live complaints
add to it in real time."
"""

import random
import sys
from datetime import date, timedelta

from app.services import report_store

# Realistic distribution across Punjab districts (weighted toward larger cities)
_DISTRICTS = [
    ("راولپنڈی", 18), ("لاہور", 16), ("فیصل آباد", 11), ("ملتان", 9),
    ("گوجرانوالہ", 8), ("سیالکوٹ", 6), ("بہاولپور", 5), ("سرگودھا", 5),
    ("جھنگ", 4), ("قصور", 4), ("شیخوپورہ", 3), ("ساہیوال", 3),
]

# Domain mix reflecting common civic complaints (police + utilities lead)
_DOMAINS = [
    ("police", 24), ("utility", 18), ("healthcare", 12), ("consumer", 11),
    ("labour", 10), ("traffic", 9), ("municipal", 8), ("education", 5),
    ("women", 3), ("rti", 2),
]


def _weighted(pairs: list[tuple[str, int]]) -> str:
    items, weights = zip(*pairs)
    return random.choices(items, weights=weights, k=1)[0]


def seed(count: int = 80) -> None:
    today = date.today()
    inserted = 0
    for i in range(count):
        domain = _weighted(_DOMAINS)
        district = _weighted(_DISTRICTS)
        # spread across the last 30 days, more weighted toward recent days
        days_ago = int(random.triangular(0, 30, 3))
        ref = f"HQD-{today.year}-{random.randint(0, 9999):04d}"
        # report_store.record stamps "today" for SQLite; for a realistic trend we
        # insert directly so created_on varies. Use the public API where dates
        # don't matter, but vary via a thin direct insert when possible.
        _record_dated(ref, domain, district, today - timedelta(days=days_ago))
        inserted += 1
    print(f"Seeded {inserted} mock reports into the reports store (NOT the vector store).")
    s = report_store.stats()
    print(f"Total now: {s['total_reports']} | top: {s['top_issues'][:3]} | districts: {len(s['districts'])}")


def _record_dated(ref: str, domain: str, district: str, when: date) -> None:
    """Insert with an explicit date so the daily trend looks real."""
    import app.services.report_store as rs

    try:
        if rs._USE_PG:
            with rs._pg().connection() as conn:
                conn.execute(
                    "INSERT INTO reports (reference_id, domain, district, created_on) "
                    "VALUES (%s, %s, %s, %s)",
                    (ref, domain, district, when),
                )
        else:
            with rs._lock, rs._sqlite() as conn:
                conn.execute(
                    "INSERT INTO reports (reference_id, domain, district, created_on) "
                    "VALUES (?, ?, ?, ?)",
                    (ref, domain, district, when.isoformat()),
                )
    except Exception as exc:  # noqa: BLE001
        print(f"  insert failed (non-fatal): {exc}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    seed(n)
