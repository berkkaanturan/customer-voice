"""
Ekşi Sözlük adapter for incremental scraping.

Ekşi Sözlük pages are sorted ascending (oldest first), so we scrape
from the last page backwards. Each topic is handled as a separate
incremental sub-source.

Includes topic discovery (search-based) from the original scraper.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from base_scraper import IncrementalScraper, RawReview, text_hash

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

# ── Topic blacklist — slugs containing these substrings will be skipped ──────
BLACKLISTED_SLUGS: set[str] = {
    "top-sakal",
}


def _is_blacklisted(slug: str) -> bool:
    """Check if a topic slug matches any blacklist entry."""
    slug_lower = slug.lower()
    return any(bl in slug_lower for bl in BLACKLISTED_SLUGS)


def _parse_eksi_date(date_str: str | None) -> str:
    """Parse Ekşi Sözlük entry date string to ISO format."""
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    if not date_str:
        return now_iso
    try:
        original_date = date_str.split("~")[0].strip()
        try:
            dt = datetime.strptime(original_date, "%d.%m.%Y %H:%M")
        except ValueError:
            dt = datetime.strptime(original_date, "%d.%m.%Y")
        tr_tz = timezone(timedelta(hours=3))
        dt = dt.replace(tzinfo=tr_tz)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception as exc:
        logger.warning("Failed to parse Ekşi Sözlük date '%s': %s", date_str, exc)
        return now_iso


def discover_eksi_topics(keywords: str = "turknet", limit: int = 10) -> list[str]:
    """Search Ekşi Sözlük for threads containing the keywords."""
    urls = [
        f"https://eksisozluk.com/basliklar/ara?searchform.keywords={keywords}&searchform.sortorder=date",
        f"https://eksisozluk.com/basliklar/ara?searchform.keywords={keywords}",
    ]

    topics: list[str] = []

    for url in urls:
        try:
            logger.info("Ekşi Sözlük: searching for topics matching '%s' via → %s", keywords, url)
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning("Ekşi Sözlük search page failed with status %d", resp.status_code)
                continue

            current_url = resp.url
            if "eksisozluk.com/" in current_url:
                path = current_url.split("eksisozluk.com/")[-1].split("?")[0]
                if "--" in path:
                    slug = path.lstrip("/")
                    logger.info("Ekşi Sözlük: redirected directly to topic '%s'", slug)
                    if slug not in topics and not _is_blacklisted(slug):
                        topics.append(slug)
                    continue

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=True)

            for a in links:
                href = a["href"]
                if "--" in href and keywords in href.lower() and href.startswith("/"):
                    slug = href.lstrip("/")
                    if slug not in topics and not _is_blacklisted(slug):
                        topics.append(slug)
        except Exception as exc:
            logger.error("Failed to fetch Ekşi Sözlük search url %s: %s", url, exc)

    if not topics:
        return [keywords]

    logger.info("Ekşi Sözlük: discovered %d unique topics matching '%s'.", len(topics), keywords)
    return topics[:limit]


class _SingleTopicScraper(IncrementalScraper):
    """Scraper for a single Ekşi Sözlük topic.

    Not used directly — EksiSozlukAdapter orchestrates multiple topics.
    """

    platform_name = "Ekşi Sözlük"
    sort_direction = "asc"

    def __init__(self, topic_slug: str):
        self.topic_slug = topic_slug
        self._resolved_slug: str | None = None
        self._total_pages: int = 0
        self._topic_title: str = ""
        self._resolved = False

    def _resolve(self) -> None:
        """Resolve redirect and discover total page count."""
        if self._resolved:
            return

        initial_url = f"https://eksisozluk.com/{self.topic_slug}"
        try:
            resp = requests.get(initial_url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(
                    "Ekşi Sözlük: topic '%s' returned status %d",
                    self.topic_slug, resp.status_code,
                )
                self._resolved = True
                return

            current_url = resp.url
            self._resolved_slug = (
                current_url.split("eksisozluk.com/")[-1]
                .split("?")[0]
                .lstrip("/")
            ) or self.topic_slug

            soup = BeautifulSoup(resp.text, "html.parser")
            pager = soup.select_one(".pager")
            self._total_pages = 1
            if pager:
                try:
                    self._total_pages = int(pager.get("data-pagecount") or 1)
                except ValueError:
                    pass

            title_el = soup.select_one("#title")
            if title_el:
                self._topic_title = title_el.get("data-title", title_el.get_text(strip=True))
            else:
                self._topic_title = self._resolved_slug.replace("-", " ").title()

            logger.info(
                "Ekşi Sözlük: resolved '%s' → '%s' (%d pages).",
                self.topic_slug, self._resolved_slug, self._total_pages,
            )
        except Exception as exc:
            logger.error(
                "Ekşi Sözlük: failed to resolve topic '%s': %s",
                self.topic_slug, exc,
            )
        self._resolved = True

    def total_pages(self) -> int:
        self._resolve()
        return self._total_pages

    def fetch_page(self, page_number: int) -> list[RawReview]:
        self._resolve()
        if not self._resolved_slug:
            return []

        url = f"https://eksisozluk.com/{self._resolved_slug}?p={page_number}"
        reviews: list[RawReview] = []

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            entries = (
                soup.select("#entry-item-list > li")
                or soup.select("ul#entry-item-list li[data-id]")
            )

            for entry in entries:
                content_el = entry.select_one("div.content")
                text = content_el.get_text(strip=True) if content_el else ""
                author_el = entry.select_one("a.entry-author")
                author = author_el.get_text(strip=True) if author_el else "Anonim"
                date_el = entry.select_one("a.entry-date")
                date_str = date_el.get_text(strip=True) if date_el else None
                entry_id = entry.get("data-id", "")
                entry_url = (
                    f"https://eksisozluk.com/entry/{entry_id}"
                    if entry_id
                    else url
                )

                if text:
                    reviews.append(
                        RawReview(
                            platform_name="Ekşi Sözlük",
                            author=author,
                            original_text=text,
                            rating=None,
                            source_url=entry_url,
                            subject=self._topic_title,
                            scraped_at=_parse_eksi_date(date_str),
                        )
                    )

        except Exception as exc:
            logger.warning(
                "Ekşi Sözlük: failed to fetch page %d of '%s': %s",
                page_number, self._resolved_slug, exc,
            )

        return reviews


class EksiSozlukAdapter(IncrementalScraper):
    """Orchestrator adapter for Ekşi Sözlük.

    Discovers multiple topic slugs and runs incremental scraping
    for each topic independently using _SingleTopicScraper.
    """

    platform_name = "Ekşi Sözlük"
    sort_direction = "asc"

    def __init__(self, search_keyword: str = "turknet", topic_limit: int = 35):
        self.search_keyword = search_keyword
        self.topic_limit = topic_limit

    # Not used directly — we override run_incremental
    def total_pages(self) -> int:
        return 0

    def fetch_page(self, page_number: int) -> list[RawReview]:
        return []

    def run_incremental(self, existing_hashes: set[str]) -> list[RawReview]:
        """Discover topics, then run incremental scrape for each."""
        topics = discover_eksi_topics(self.search_keyword, limit=self.topic_limit)
        all_new: list[RawReview] = []

        for topic_slug in topics:
            logger.info("Ekşi Sözlük: scraping topic '%s'…", topic_slug)
            topic_scraper = _SingleTopicScraper(topic_slug)
            topic_new = topic_scraper.run_incremental(existing_hashes)
            all_new.extend(topic_new)
            logger.info(
                "Ekşi Sözlük ('%s'): %d new reviews.", topic_slug, len(topic_new),
            )

        logger.info(
            "[%s] Incremental scrape complete: %d new reviews across %d topics.",
            self.platform_name, len(all_new), len(topics),
        )
        return all_new
