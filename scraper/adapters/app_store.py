"""
App Store adapter (v2 — ID watermark incremental).

Uses Apple's public RSS JSON feed (sortBy=mostRecent) which gives up to
10 pages of 50 reviews (500 newest reviews).
Every review has a permanent unique ID (entry.id.label).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from base_scraper import IncrementalScraper, RawReview, ScrapeContext
from http_client import HttpClient

logger = logging.getLogger(__name__)


class AppStoreAdapter(IncrementalScraper):
    platform_name = "App Store"

    def __init__(self, app_id: int = 1001052556, country: str = "tr") -> None:
        super().__init__()
        self.app_id = app_id
        self.country = country
        self.http = HttpClient("App Store", min_delay=1.0, max_delay=2.5, retries=3)

    def _fetch_page(self, page_number: int) -> list[RawReview]:
        url = (
            f"https://itunes.apple.com/{self.country}/rss/customerreviews/"
            f"page={page_number}/id={self.app_id}/sortBy=mostRecent/json"
        )
        resp = self.http.get(url, allow_404=True)
        if resp.status_code != 200:
            return []

        data = resp.json()
        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        if not entries:
            return []

        reviews: list[RawReview] = []
        for entry in entries:
            # Skip app metadata entry (first entry on page 1)
            if "im:name" in entry:
                continue

            ext_id = str(entry.get("id", {}).get("label") or "").strip()
            author = entry.get("author", {}).get("name", {}).get("label", "Anonim")
            content = entry.get("content", {}).get("label", "")
            title = entry.get("title", {}).get("label", "")
            rating_str = entry.get("im:rating", {}).get("label", "0")
            try:
                rating = int(rating_str)
            except ValueError:
                rating = None

            full_text = f"{title}\n{content}" if title else content
            if not full_text.strip():
                continue

            date_str = entry.get("updated", {}).get("label") or datetime.now(timezone.utc).isoformat()

            reviews.append(
                RawReview(
                    platform_name=self.platform_name,
                    external_id=ext_id,
                    author=author,
                    original_text=full_text.strip(),
                    rating=rating,
                    source_url=f"https://apps.apple.com/{self.country}/app/turknet/id{self.app_id}",
                    scraped_at=date_str,
                )
            )

        return reviews

    def run_incremental(self, ctx: ScrapeContext) -> list[RawReview]:
        source_key = "default"
        errors: list[str] = []
        all_new: list[RawReview] = []

        try:
            all_new = self.scan_pages(
                ctx,
                source_key,
                range(1, 11),
                self._fetch_page,
                label=f"App Store/{self.app_id}",
                max_pages=10,
            )
        except Exception as exc:
            logger.error("App Store: failed: %s", exc, exc_info=True)
            errors.append(str(exc))

        self.stats = {
            "requests": self.http.request_count,
            "new_reviews": len(all_new),
            "errors": errors,
        }
        return all_new
