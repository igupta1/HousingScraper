import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List

from .models import Listing, now_utc

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    dedup_key   TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    listing_id  TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT,
    price       INTEGER,
    bedrooms    INTEGER,
    bathrooms   REAL,
    neighborhood TEXT,
    address     TEXT,
    first_seen  TEXT NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_listings_notified ON listings(notified);
"""


@contextmanager
def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_new(db_path: Path, listings: Iterable[Listing]) -> List[Listing]:
    """Insert listings we've never seen. Returns the subset that was actually new."""
    inserted: List[Listing] = []
    timestamp = now_utc().isoformat()
    with _connect(db_path) as conn:
        for listing in listings:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO listings
                  (dedup_key, source, listing_id, url, title, price, bedrooms,
                   bathrooms, neighborhood, address, first_seen, notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    listing.dedup_key,
                    listing.source,
                    listing.listing_id,
                    listing.url,
                    listing.title,
                    listing.price,
                    listing.bedrooms,
                    listing.bathrooms,
                    listing.neighborhood,
                    listing.address,
                    timestamp,
                ),
            )
            if cur.rowcount > 0:
                inserted.append(listing)
    return inserted


def fetch_pending_notifications(db_path: Path) -> List[Listing]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE notified = 0 ORDER BY first_seen ASC"
        ).fetchall()
    return [_row_to_listing(r) for r in rows]


def mark_notified(db_path: Path, dedup_keys: Iterable[str]) -> None:
    keys = list(dedup_keys)
    if not keys:
        return
    with _connect(db_path) as conn:
        conn.executemany(
            "UPDATE listings SET notified = 1 WHERE dedup_key = ?",
            [(k,) for k in keys],
        )


def _row_to_listing(row: sqlite3.Row) -> Listing:
    return Listing(
        source=row["source"],
        listing_id=row["listing_id"],
        url=row["url"],
        title=row["title"] or "",
        price=row["price"],
        bedrooms=row["bedrooms"],
        bathrooms=row["bathrooms"],
        neighborhood=row["neighborhood"],
        address=row["address"],
    )
