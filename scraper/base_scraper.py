"""
Base classes for incremental, platform-agnostic review scraping.

Design (v2 — ID watermark)
--------------------------
* Every review carries a stable ``external_id`` (Ekşi entry id, Play Store
  reviewId, App Store review id, Şikayetvar complaint path).
* ``ScrapeContext`` holds, per platform, the set of IDs already in the DB plus
  the text hashes of *legacy* rows that were stored before IDs existed.
* Sources are scanned from newest → oldest.  A page is "exhausted" when every
  review on it is already known or older than the cutoff.  The scan stops after
  ``overlap_pages + 1`` consecutive exhausted pages — so one known review on a
  partially-new page never stops the scan early.
* Cutoff:
    - ``--backfill-since`` date when given (known reviews never stop the scan),
    - otherwise, for a source that has never been scraped, ``now - initial_lookback_days``,
    - otherwise none (stop purely on known IDs).
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, TypedDict

logger = logging.getLogger(__name__)


# ── Shared type for a single raw review ──────────────────────────────────────

class RawReview(TypedDict, total=False):
    """Standardised review record coming out of any platform adapter."""
    platform_name: str
    external_id: str
    author: str
    original_text: str
    rating: int | None
    source_url: str
    scraped_at: str          # ISO-8601 date of the review itself
    subject: str | None
    category: str | None


def text_hash(text: str) -> str:
    """SHA-256 hex digest of stripped text — must match db._text_hash."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ── Run context ──────────────────────────────────────────────────────────────

@dataclass
class ScrapeContext:
    known_ids: dict[str, set[str]] = field(default_factory=dict)
    legacy_hashes: dict[str, set[str]] = field(default_factory=dict)
    state: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    backfill_since: datetime | None = None
    initial_lookback_days: int = 180
    overlap_pages: int = 1
    state_updates: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    # -- dedup ---------------------------------------------------------------
    def is_known(self, review: RawReview) -> bool:
        platform = review.get("platform_name", "")
        ext = review.get("external_id")
        if ext and ext in self.known_ids.get(platform, set()):
            return True
        h = text_hash(review.get("original_text", ""))
        return h in self.legacy_hashes.get(platform, set())

    def mark_seen(self, review: RawReview) -> None:
        platform = review.get("platform_name", "")
        ext = review.get("external_id")
        if ext:
            self.known_ids.setdefault(platform, set()).add(ext)

    # -- state ---------------------------------------------------------------
    def get_state(self, platform: str, source_key: str) -> dict[str, Any] | None:
        return self.state.get((platform, source_key))

    def update_state(self, platform: str, source_key: str, **fields: Any) -> None:
        current = self.state_updates.setdefault(
            (platform, source_key),
            {"platform_name": platform, "source_key": source_key},
        )
        current.update({k: v for k, v in fields.items() if v is not None})

    def cutoff_for(self, platform: str, source_key: str) -> datetime | None:
        if self.backfill_since:
            return self.backfill_since
        if self.get_state(platform, source_key) is None:
            # Never tracked → bounded lookback so a brand-new source doesn't
            # crawl its entire history on the daily job.
            return datetime.now(timezone.utc) - timedelta(days=self.initial_lookback_days)
        return None


# ── Abstract base class ─────────────────────────────────────────────────────

class IncrementalScraper(ABC):
    """Platform adapter interface.  Subclasses implement ``run_incremental``."""

    platform_name: str = ""

    def __init__(self) -> None:
        self.stats: dict[str, Any] = {}

    @abstractmethod
    def run_incremental(self, ctx: ScrapeContext) -> list[RawReview]:
        """Return new (unseen) reviews and record state via ``ctx.update_state``."""

    # ── shared page-scan engine ───────────────────────────────────────────
    def scan_pages(
        self,
        ctx: ScrapeContext,
        source_key: str,
        pages: Iterable[Any],
        fetch: Callable[[Any], list[RawReview]],
        *,
        label: str | None = None,
        max_pages: int | None = None,
    ) -> list[RawReview]:
        """Scan ``pages`` (newest page first) until exhausted.

        ``fetch(page)`` returns the reviews of one page (any order).
        Updates ``ctx`` state for ``source_key`` with the newest ID / date seen.
        """
        label = label or f"{self.platform_name}/{source_key}"
        cutoff = ctx.cutoff_for(self.platform_name, source_key)
        backfill = ctx.backfill_since is not None

        new_reviews: list[RawReview] = []
        exhausted_streak = 0
        pages_scanned = 0
        newest_dt: datetime | None = None
        newest_id: str | None = None

        for page in pages:
            if max_pages is not None and pages_scanned >= max_pages:
                logger.warning("[%s] max_pages=%d reached — stopping.", label, max_pages)
                break

            page_reviews = fetch(page)
            pages_scanned += 1
            if not page_reviews:
                logger.info("[%s] page %s empty — end of source.", label, page)
                break

            page_new = 0
            page_old = 0
            for review in page_reviews:
                dt = parse_iso(review.get("scraped_at"))
                if dt and (newest_dt is None or dt > newest_dt):
                    newest_dt = dt
                    newest_id = review.get("external_id") or newest_id

                if cutoff and dt and dt < cutoff:
                    page_old += 1
                    continue
                if ctx.is_known(review):
                    continue
                ctx.mark_seen(review)
                new_reviews.append(review)
                page_new += 1

            known = len(page_reviews) - page_new - page_old
            logger.info(
                "[%s] page %s: %d fetched, %d new, %d known, %d older than cutoff.",
                label, page, len(page_reviews), page_new, known, page_old,
            )

            if backfill:
                # In backfill mode only the date cutoff stops the scan
                exhausted = page_old == len(page_reviews)
            else:
                exhausted = page_new == 0
            if page_old == len(page_reviews):
                logger.info("[%s] whole page older than cutoff — stopping.", label)
                break

            exhausted_streak = exhausted_streak + 1 if exhausted else 0
            if exhausted_streak > ctx.overlap_pages:
                logger.info("[%s] %d consecutive exhausted pages — stopping.", label, exhausted_streak)
                break

        prev = ctx.get_state(self.platform_name, source_key) or {}
        prev_dt = parse_iso(prev.get("last_seen_at"))
        if newest_dt and (prev_dt is None or newest_dt > prev_dt):
            ctx.update_state(
                self.platform_name, source_key,
                last_seen_at=newest_dt.isoformat(),
                last_external_id=newest_id,
            )
        else:
            ctx.update_state(self.platform_name, source_key)  # touch updated_at

        logger.info("[%s] done: %d pages, %d new reviews.", label, pages_scanned, len(new_reviews))
        return new_reviews
