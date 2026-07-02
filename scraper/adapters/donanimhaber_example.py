"""
Donanım Haber forum adapter — EXAMPLE / SKELETON.

Demonstrates how to add a new platform with zero changes to
the engine or stop-condition logic.  Just implement total_pages()
and fetch_page() and register the adapter in main.py.

Usage:
    adapter = DonanımHaberAdapter(thread_id=12345)
    new_reviews = adapter.run_incremental(existing_hashes)
"""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from base_scraper import IncrementalScraper, RawReview

logger = logging.getLogger(__name__)


class DonanımHaberAdapter(IncrementalScraper):
    """Skeleton adapter for Donanım Haber forum threads.

    Forum threads are typically sorted ASC (oldest post first),
    so we traverse from the last page backwards to find new posts.
    """

    platform_name = "Donanım Haber"
    sort_direction = "asc"  # forum posts: oldest first

    def __init__(self, thread_id: int, base_url: str = "https://forum.donanimhaber.com"):
        self.thread_id = thread_id
        self.base_url = base_url
        self._total: int | None = None

    def total_pages(self) -> int:
        """Discover total page count from the thread's first page."""
        if self._total is not None:
            return self._total

        # TODO: Implement actual page count discovery
        # url = f"{self.base_url}/thread/{self.thread_id}"
        # resp = requests.get(url, timeout=15)
        # soup = BeautifulSoup(resp.text, "html.parser")
        # self._total = int(soup.select_one(".pager-last")["data-page"])
        self._total = 0  # placeholder
        return self._total

    def fetch_page(self, page_number: int) -> list[RawReview]:
        """Fetch posts from a single forum page."""
        # TODO: Implement actual parsing
        # url = f"{self.base_url}/thread/{self.thread_id}?page={page_number}"
        # resp = requests.get(url, timeout=15)
        # soup = BeautifulSoup(resp.text, "html.parser")
        # ...parse posts into RawReview dicts...
        return []
