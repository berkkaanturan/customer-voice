"""
Play Store adapter for incremental scraping.

Uses google-play-scraper which is count-based (not page-based).
We treat the entire fetch as a single "page" and rely on the hash engine
to filter out already-known reviews.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from base_scraper import IncrementalScraper, RawReview

logger = logging.getLogger(__name__)


class PlayStoreAdapter(IncrementalScraper):
    """Incremental adapter for Google Play Store reviews.

    google-play-scraper fetches reviews by `count` rather than pages.
    We model this as a single "page" that returns up to `count` reviews,
    sorted by NEWEST. The base engine's hash check handles deduplication.
    """

    platform_name = "Play Store"
    sort_direction = "desc"

    def __init__(self, app_id: str = "com.turknet.oim", count: int = 500):
        self.app_id = app_id
        self.count = count

    def total_pages(self) -> int:
        """Play Store API is count-based — we model it as 1 logical page."""
        return 1

    def fetch_page(self, page_number: int) -> list[RawReview]:
        """Fetch reviews from Google Play Store using google-play-scraper.

        Iterates over rating scores (1-5) and NEWEST sort to maximise
        historical coverage within a single logical fetch.
        """
        try:
            from google_play_scraper import Sort, reviews as gp_reviews
        except ImportError:
            logger.error("google-play-scraper is not installed.")
            return []

        reviews: list[RawReview] = []

        scores = [1, 2, 3, 4, 5]
        count_per_score = max(50, self.count // len(scores))

        for score in scores:
            try:
                logger.info(
                    "Play Store: score=%d, sort=NEWEST, count=%d...",
                    score, count_per_score,
                )
                result, _ = gp_reviews(
                    self.app_id,
                    lang="tr",
                    country="tr",
                    sort=Sort.NEWEST,
                    count=count_per_score,
                    filter_score_with=score,
                )
                if not result:
                    continue

                for r in result:
                    scraped_at = (
                        r["at"].replace(tzinfo=timezone.utc).isoformat()
                        if isinstance(r.get("at"), datetime)
                        else datetime.now(tz=timezone.utc).isoformat()
                    )
                    reviews.append(
                        RawReview(
                            platform_name="Play Store",
                            author=r.get("userName", "Anonim"),
                            original_text=r.get("content", ""),
                            rating=r.get("score"),
                            source_url=f"https://play.google.com/store/apps/details?id={self.app_id}",
                            scraped_at=scraped_at,
                        )
                    )
            except Exception as exc:
                logger.error(
                    "Play Store (score=%d) failed: %s", score, exc,
                )

        logger.info("Play Store: fetched %d reviews total.", len(reviews))
        return reviews
