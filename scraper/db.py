"""
Database module for the Customer Voice Dashboard.

Provides Supabase client initialisation and helper functions for
inserting and querying review records.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from config import SUPABASE_SECRET_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

# ── Supabase client singleton ─────────────────────────────────────────────────
_supabase: Client | None = None

TABLE_NAME = "reviews"


def get_supabase_client() -> Client:
    """Return a lazily-initialised Supabase client.

    Uses the service-role (secret) key so we can bypass RLS for inserts.
    """
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in the environment."
            )
        _supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        logger.info("Supabase client initialised (%s).", SUPABASE_URL)
    return _supabase


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_hash(text: str) -> str:
    """Return a SHA-256 hex digest for deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


# ── Public API ────────────────────────────────────────────────────────────────

def get_existing_hashes() -> set[str]:
    """Fetch all existing text_hash values from the reviews table.

    Returns:
        A set of SHA-256 hex strings already stored in the database.
    """
    client = get_supabase_client()
    try:
        page = 0
        limit = 1000
        hashes = set()
        while True:
            result = (
                client.table(TABLE_NAME)
                .select("text_hash")
                .order("created_at")
                .range(page * limit, (page + 1) * limit - 1)
                .execute()
            )
            data = result.data or []
            for row in data:
                h = row.get("text_hash")
                if h:
                    hashes.add(h)
            if len(data) < limit:
                break
            page += 1
        logger.info("Loaded %d existing hashes from DB.", len(hashes))
        return hashes
    except Exception as exc:
        logger.error("Failed to fetch existing hashes: %s", exc)
        return set()


def _paged_select(table: str, columns: str, apply_filters=None, order: str = "id") -> list[dict[str, Any]]:
    """Fetch all rows of a query in 1000-row pages."""
    client = get_supabase_client()
    rows: list[dict[str, Any]] = []
    page, limit = 0, 1000
    while True:
        q = client.table(table).select(columns)
        if apply_filters:
            q = apply_filters(q)
        data = q.order(order).range(page * limit, (page + 1) * limit - 1).execute().data or []
        rows.extend(data)
        if len(data) < limit:
            return rows
        page += 1


def get_known_ids() -> dict[str, set[str]]:
    """Return {platform_name: {external_id, ...}} for all rows that have an ID.

    Raises a clear error if migration 001 has not been applied.
    """
    try:
        rows = _paged_select(
            TABLE_NAME, "platform_name, external_id",
            lambda q: q.not_.is_("external_id", "null"),
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not read reviews.external_id — run "
            "supabase/migrations/001_external_id_and_scrape_state.sql first. "
            f"Original error: {exc}"
        ) from exc
    known: dict[str, set[str]] = {}
    for r in rows:
        known.setdefault(r["platform_name"], set()).add(str(r["external_id"]))
    logger.info("Loaded known IDs: %s", {k: len(v) for k, v in known.items()})
    return known


def get_legacy_hashes() -> dict[str, set[str]]:
    """Text hashes of legacy rows (no external_id), grouped by platform.

    Used only to avoid re-inserting reviews stored before IDs existed.
    """
    rows = _paged_select(
        TABLE_NAME, "platform_name, text_hash",
        lambda q: q.is_("external_id", "null"),
    )
    legacy: dict[str, set[str]] = {}
    for r in rows:
        if r.get("text_hash"):
            legacy.setdefault(r["platform_name"], set()).add(r["text_hash"])
    logger.info("Loaded legacy hashes: %s", {k: len(v) for k, v in legacy.items()})
    return legacy


def get_scrape_state() -> dict[tuple[str, str], dict[str, Any]]:
    """Return {(platform_name, source_key): row} from scrape_state."""
    rows = _paged_select("scrape_state", "*", order="platform_name")
    return {(r["platform_name"], r["source_key"]): r for r in rows}


def save_scrape_state(updates: list[dict[str, Any]]) -> None:
    """Upsert scrape_state rows."""
    if not updates:
        return
    client = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    rows = [{**u, "updated_at": now} for u in updates]
    for i in range(0, len(rows), 200):
        client.table("scrape_state").upsert(
            rows[i : i + 200], on_conflict="platform_name,source_key",
        ).execute()
    logger.info("Saved %d scrape_state rows.", len(rows))


def get_recent_logs(limit: int = 5) -> list[dict[str, Any]]:
    client = get_supabase_client()
    try:
        res = (
            client.table("scraper_logs")
            .select("started_at, status, platform_stats")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.warning("Could not read scraper_logs: %s", exc)
        return []


def save_reviews(reviews: list[dict[str, Any]]) -> tuple[int, int]:
    """Upsert reviews into Supabase.

    Dedup is done by the adapters (ID watermark); the DB enforces it again with
    UNIQUE (platform_name, external_id) + ``ignore_duplicates`` so re-running
    the pipeline is always safe.

    Returns:
        (rows_sent_successfully, rows_failed)
    """
    if not reviews:
        logger.info("No reviews to save.")
        return 0, 0

    client = get_supabase_client()
    rows_to_insert: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for review in reviews:
        text = review.get("original_text", "")
        platform = review.get("platform_name", "Unknown")
        ext = review.get("external_id")
        if ext:
            key = (platform, str(ext))
            if key in seen:
                continue
            seen.add(key)

        row: dict[str, Any] = {
            "platform_name": platform,
            "external_id": str(ext) if ext else None,
            "author": (review.get("author") or "Anonim")[:255],
            "original_text": text,
            "text_hash": _text_hash(text),
            "sentiment": review.get("sentiment", "Negative"),
            "category": review.get("category") or "Genel",
            "rating": review.get("rating"),
            "source_url": review.get("source_url"),
            "subject": (review.get("subject") or None) and review["subject"][:255],
            "keywords": review.get("keywords", []),
        }
        if review.get("scraped_at"):
            row["scraped_at"] = review["scraped_at"]
        rows_to_insert.append(row)

    inserted = 0
    failed = 0
    chunk_size = 100
    for i in range(0, len(rows_to_insert), chunk_size):
        chunk = rows_to_insert[i : i + chunk_size]
        try:
            client.table(TABLE_NAME).upsert(
                chunk,
                on_conflict="platform_name,external_id",
                ignore_duplicates=True,
            ).execute()
            inserted += len(chunk)
            logger.info("Upserted chunk %d–%d (%d rows).", i + 1, i + len(chunk), len(chunk))
        except Exception as exc:
            failed += len(chunk)
            logger.error("Failed to upsert chunk %d–%d: %s", i + 1, i + len(chunk), exc)

    logger.info("Total saved: %d, failed: %d.", inserted, failed)
    return inserted, failed


def clear_all_reviews() -> bool:
    """Delete all rows from the reviews table."""
    client = get_supabase_client()
    try:
        # Delete all records using a tautology on UUID id
        client.table(TABLE_NAME).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        logger.info("Successfully cleared all reviews from Supabase.")
        return True
    except Exception as exc:
        logger.error("Failed to clear reviews table: %s", exc)
        return False


def get_latest_review_date(platform: str) -> str | None:
    """Get the most recent scraped_at for a given platform.

    Useful for incremental scraping — only fetch reviews newer than this.

    Args:
        platform: The platform_name value (e.g. "Play Store").

    Returns:
        ISO date string of the latest review, or None if no reviews exist.
    """
    client = get_supabase_client()
    try:
        result = (
            client.table(TABLE_NAME)
            .select("scraped_at")
            .eq("platform_name", platform)
            .order("scraped_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("scraped_at")
        return None
    except Exception as exc:
        logger.error("Failed to get latest review date for %s: %s", platform, exc)
        return None

def save_scraper_log(log_data: dict[str, Any]) -> bool:
    """Save execution metrics to the scraper_logs table.
    
    Expected keys:
        started_at: str (ISO)
        completed_at: str (ISO)
        total_duration_seconds: float
        status: str ('success' or 'error')
        error_message: str | None
        platform_stats: dict
    """
    client = get_supabase_client()
    try:
        client.table("scraper_logs").insert(log_data).execute()
        logger.info("Successfully saved scraper log to database.")
        return True
    except Exception as exc:
        logger.error("Failed to save scraper log: %s", exc)
        return False
