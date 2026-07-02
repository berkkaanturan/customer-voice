"""
App Store adapter for incremental scraping.

Uses Apple's public RSS/JSON feed with sortBy=mostRecent (DESC).
Maximum 10 pages, 50 reviews per page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from base_scraper import IncrementalScraper, RawReview

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class AppStoreAdapter(IncrementalScraper):
    """Incremental adapter for Apple App Store reviews via RSS feed.

    RSS endpoint: itunes.apple.com/{country}/rss/customerreviews/
                  page={n}/id={app_id}/sortBy=mostRecent/json

    Sort: mostRecent → page 1 has the newest reviews → DESC.
    Apple limits: max 10 pages, ~50 reviews per page.
    """

    platform_name = "App Store"
    sort_direction = "desc"

    def __init__(self, app_id: int = 1001052556, country: str = "tr"):
        self.app_id = app_id
        self.country = country

    def total_pages(self) -> int:
        """Apple RSS supports up to 10 pages."""
        return 10

    def fetch_page(self, page_number: int) -> list[RawReview]:
        """Fetch a single RSS page of App Store reviews."""
        url = (
            f"https://itunes.apple.com/{self.country}/rss/customerreviews/"
            f"page={page_number}/id={self.app_id}/sortBy=mostRecent/json"
        )
        reviews: list[RawReview] = []

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(
                    "App Store RSS page %d returned status %d",
                    page_number, resp.status_code,
                )
                return []

            data = resp.json()
            feed = data.get("feed", {})
            entries = feed.get("entry", [])

            if isinstance(entries, dict):
                entries = [entries]

            if not entries:
                return []

            for entry in entries:
                # Skip app metadata entry (first entry on page 1)
                if "im:name" in entry:
                    continue

                author = entry.get("author", {}).get("name", {}).get("label", "Anonim")
                content = entry.get("content", {}).get("label", "")
                title = entry.get("title", {}).get("label", "")
                rating_str = entry.get("im:rating", {}).get("label", "0")

                try:
                    rating = int(rating_str)
                except ValueError:
                    rating = None

                full_text = f"{title}\n{content}" if title else content

                reviews.append(
                    RawReview(
                        platform_name="App Store",
                        author=author,
                        original_text=full_text.strip(),
                        rating=rating,
                        source_url=f"https://apps.apple.com/{self.country}/app/turknet/id{self.app_id}",
                        scraped_at=(
                            entry.get("updated", {}).get("label")
                            or datetime.now(tz=timezone.utc).isoformat()
                        ),
                    )
                )

        except Exception as exc:
            logger.error("App Store RSS page %d failed: %s", page_number, exc)

        return reviews
