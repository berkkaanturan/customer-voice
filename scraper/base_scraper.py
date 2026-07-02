"""
Base class for incremental, platform-agnostic review scraping.

Provides an abstract interface that platform adapters must implement,
plus a shared engine (`run_incremental`) that uses text-hash deduplication
to stop scraping as soon as it encounters reviews already stored in the DB.
"""

from __future__ import annotations

import hashlib
import logging
import time
import random
from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict

logger = logging.getLogger(__name__)


# ── Shared type for a single raw review ──────────────────────────────────────

class RawReview(TypedDict, total=False):
    """Standardised review record coming out of any platform adapter."""
    platform_name: str
    author: str
    original_text: str
    rating: int | None
    source_url: str
    scraped_at: str
    subject: str | None
    category: str | None


def text_hash(text: str) -> str:
    """SHA-256 hex digest of stripped text — must match db._text_hash."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


# ── Abstract base class ─────────────────────────────────────────────────────

class IncrementalScraper(ABC):
    """Platform-agnostic incremental scraper base class.

    Subclasses must set:
        platform_name   – display name stored in DB (e.g. "Play Store")
        sort_direction   – "asc" or "desc" (verified in Adım 0)

    And implement:
        total_pages()    – how many pages exist for this source
        fetch_page(n)    – return reviews from page *n* (1-indexed)
    """

    platform_name: str = ""
    sort_direction: Literal["asc", "desc"] = "desc"

    # Throttle settings (seconds)
    min_delay: float = 2.0
    max_delay: float = 5.0

    # ── Abstract interface ────────────────────────────────────────────────

    @abstractmethod
    def total_pages(self) -> int:
        """Return the total number of pages available for this source."""

    @abstractmethod
    def fetch_page(self, page_number: int) -> list[RawReview]:
        """Fetch all reviews from a single page (1-indexed)."""

    # ── Shared engine ─────────────────────────────────────────────────────

    def run_incremental(self, existing_hashes: set[str]) -> list[RawReview]:
        """Platform-agnostic incremental scraping engine.

        Traversal order is determined by `sort_direction`:
          • desc → page 1, 2, 3 … (newest first)
          • asc  → page N, N-1, N-2 … (start from last page, go backwards)

        **Stop condition (hash-based):**
        When a page contains *any* review whose text_hash is already in
        `existing_hashes`, the engine collects new reviews from that page
        and then stops — no further pages are fetched.

        Returns:
            List of new (unseen) RawReview dicts.
        """
        total = self.total_pages()
        if total <= 0:
            logger.info("[%s] No pages to scrape.", self.platform_name)
            return []

        # Build page traversal order
        if self.sort_direction == "desc":
            pages = list(range(1, total + 1))
        else:  # asc → start from the last page
            pages = list(range(total, 0, -1))

        logger.info(
            "[%s] Starting incremental scrape: %d pages available, "
            "direction=%s, traversal=%s…%s",
            self.platform_name, total, self.sort_direction,
            pages[0], pages[-1],
        )

        new_reviews: list[RawReview] = []
        pages_scanned = 0
        stop = False

        for page_num in pages:
            if stop:
                break

            page_reviews = self.fetch_page(page_num)
            pages_scanned += 1

            if not page_reviews:
                logger.info("[%s] Page %d returned 0 reviews — skipping.", self.platform_name, page_num)
                # For DESC sources, empty page means no more data
                if self.sort_direction == "desc":
                    break
                continue

            page_new = 0
            found_known = False
            for review in page_reviews:
                h = text_hash(review.get("original_text", ""))
                if h in existing_hashes:
                    found_known = True
                else:
                    new_reviews.append(review)
                    existing_hashes.add(h)  # prevent intra-run dupes
                    page_new += 1

            logger.info(
                "[%s] Page %d: %d reviews fetched, %d new, %d known.",
                self.platform_name, page_num,
                len(page_reviews), page_new,
                len(page_reviews) - page_new,
            )

            if found_known:
                logger.info(
                    "[%s] Known hash found on page %d — stopping "
                    "(all newer content collected).",
                    self.platform_name, page_num,
                )
                stop = True

            # Throttle between pages
            if not stop and pages_scanned < len(pages):
                delay = random.uniform(self.min_delay, self.max_delay)
                time.sleep(delay)

        logger.info(
            "[%s] Incremental scrape complete: %d pages scanned, "
            "%d new reviews collected.",
            self.platform_name, pages_scanned, len(new_reviews),
        )
        return new_reviews
