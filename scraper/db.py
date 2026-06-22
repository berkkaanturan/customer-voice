"""
Database module for the Customer Voice Dashboard.

Provides Supabase client initialisation and helper functions for
inserting and querying review records.
"""

from __future__ import annotations

import hashlib
import logging
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


def save_reviews(reviews: list[dict[str, Any]]) -> int:
    """Insert reviews into Supabase, skipping duplicates by text hash.

    Each review dict is expected to have at least:
        - platform_name, author, original_text
        - sentiment, category  (added by analyzer)

    Optional keys: rating, source_url, scraped_at

    Args:
        reviews: List of enriched review dicts.

    Returns:
        Number of new rows actually inserted.
    """
    if not reviews:
        logger.info("No reviews to save.")
        return 0

    client = get_supabase_client()
    existing_hashes = get_existing_hashes()

    rows_to_insert: list[dict[str, Any]] = []

    for review in reviews:
        text = review.get("original_text", "")
        h = _text_hash(text)

        if h in existing_hashes:
            continue

        row: dict[str, Any] = {
            "platform_name": review.get("platform_name", "Unknown"),
            "author": review.get("author", "Anonim"),
            "original_text": text,
            "text_hash": h,
            "sentiment": review.get("sentiment", "Neutral"),
            "category": review.get("category", "Genel"),
            "rating": review.get("rating"),
            "source_url": review.get("source_url"),
            "subject": review.get("subject"),
        }

        # If a specific scraped_at timestamp was provided, use it;
        # otherwise let the DB default (now()) handle it.
        if review.get("scraped_at"):
            row["scraped_at"] = review["scraped_at"]

        rows_to_insert.append(row)
        existing_hashes.add(h)  # prevent intra-batch dupes

    if not rows_to_insert:
        logger.info("All reviews already exist in DB — nothing to insert.")
        return 0

    # Batch insert in chunks of 100 (Supabase limit is ~1000 but smaller is safer)
    inserted = 0
    chunk_size = 100
    for i in range(0, len(rows_to_insert), chunk_size):
        chunk = rows_to_insert[i : i + chunk_size]
        try:
            client.table(TABLE_NAME).insert(chunk).execute()
            inserted += len(chunk)
            logger.info(
                "Inserted chunk %d–%d (%d rows).",
                i + 1,
                i + len(chunk),
                len(chunk),
            )
        except Exception as exc:
            logger.error(
                "Failed to insert chunk %d–%d: %s", i + 1, i + len(chunk), exc
            )

    logger.info("Total inserted: %d / %d new reviews.", inserted, len(rows_to_insert))
    return inserted


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
