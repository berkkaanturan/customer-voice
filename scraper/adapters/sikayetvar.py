"""
Şikayetvar adapter for incremental scraping.

Scrapes the TürkNet brand page across 22 complaint categories plus the
general listing.  Each category is treated as a separate incremental
sub-source with its own page traversal.

Default sort: newest first → DESC.
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

# ── All Şikayetvar categories for TürkNet ────────────────────────────────────
SIKAYETVAR_CATEGORIES: dict[str, str] = {
    "abonelik": "Abonelik",
    "adres-degisikligi": "Adres Değişikliği",
    "adsl": "ADSL",
    "altyapi": "Altyapı",
    "altyapisiz-internet": "Altyapısız İnternet",
    "ariza": "Arıza",
    "bakim-calismasi": "Bakım Çalışması",
    "dondurma-islemi": "Dondurma İşlemi",
    "ev-telefonu-hizmeti": "Ev Telefonu Hizmeti",
    "evde-internet": "Evde İnternet",
    "fatura": "Fatura",
    "fiber-internet": "Fiber İnternet",
    "gezgin-internet": "Gezgin İnternet",
    "gigafiber": "Gigafiber",
    "hiz-testi": "Hız Testi",
    "internet-kesintisi": "İnternet Kesintisi",
    "internet-paketleri": "İnternet Paketleri",
    "modem": "Modem",
    "online-islemler": "Online İşlemler",
    "ping-sorunu": "Ping Sorunu",
    "vdsl": "VDSL",
    "yalin-internet": "Yalın İnternet",
}


def _parse_turkish_date(date_str: str | None) -> str:
    """Parse Turkish relative or absolute dates to ISO format."""
    now = datetime.now(tz=timezone.utc)
    if not date_str:
        return now.isoformat()

    date_str = date_str.lower().strip()

    if "saat önce" in date_str or "saat once" in date_str:
        try:
            hours = int(date_str.split()[0])
            return (now - timedelta(hours=hours)).isoformat()
        except Exception:
            pass
    elif "dakika önce" in date_str or "dakika once" in date_str:
        try:
            mins = int(date_str.split()[0])
            return (now - timedelta(minutes=mins)).isoformat()
        except Exception:
            pass
    elif "dün" in date_str or "dun" in date_str:
        return (now - timedelta(days=1)).isoformat()

    months = {
        "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
        "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
        "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
        "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
    }

    parts = date_str.split()
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            month = months.get(parts[1], 1)
            year = now.year
            hour = 0
            minute = 0
            for p in parts[2:]:
                if p.isdigit() and len(p) == 4:
                    year = int(p)
                elif ":" in p:
                    h_m = p.split(":")
                    if len(h_m) == 2:
                        hour = int(h_m[0])
                        minute = int(h_m[1])
            tr_tz = timezone(timedelta(hours=3))
            dt = datetime(year, month, day, hour, minute, tzinfo=tr_tz)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception as exc:
            logger.warning("Failed to parse Turkish date '%s': %s", date_str, exc)

    return now.isoformat()


def _parse_page(html: str, url: str, category: str) -> list[RawReview]:
    """Parse complaint cards from an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article") or soup.select(".complaint-card")
    reviews: list[RawReview] = []

    for card in cards:
        title_el = card.select_one("h3 a")
        subject = title_el.get_text(strip=True) if title_el else ""
        relative_url = title_el.get("href", "") if title_el else ""
        source_url = (
            f"https://www.sikayetvar.com{relative_url}"
            if relative_url
            else url
        )
        author_el = card.select_one("header span.font-bold")
        author = author_el.get_text(strip=True) if author_el else "Anonim"
        date_el = card.select_one("header span.text-zinc-500")
        date_str = date_el.get_text(strip=True) if date_el else None
        text_el = card.select_one("p.wrap-anywhere") or card.select_one("p")
        text = text_el.get_text(strip=True) if text_el else ""

        if text:
            reviews.append(
                RawReview(
                    platform_name="Şikayetvar",
                    author=author,
                    original_text=text,
                    rating=None,
                    source_url=source_url,
                    subject=subject,
                    category=category,
                    scraped_at=_parse_turkish_date(date_str),
                )
            )

    return reviews


class SikayetvarAdapter(IncrementalScraper):
    """Incremental adapter for Şikayetvar.

    Since Şikayetvar has 22+ categories and each has its own page
    sequence, we override `run_incremental` to handle per-category
    incremental logic independently.
    """

    platform_name = "Şikayetvar"
    sort_direction = "desc"

    # Maximum pages to scan per category before giving up
    MAX_PAGES_PER_CATEGORY = 50

    def __init__(self, brand_slug: str = "turknet"):
        self.brand_slug = brand_slug

    # These are not used directly since we override run_incremental,
    # but are required by the ABC.
    def total_pages(self) -> int:
        return 0

    def fetch_page(self, page_number: int) -> list[RawReview]:
        return []

    def _fetch_category_page(
        self, cat_slug: str | None, cat_name: str, page: int,
    ) -> list[RawReview]:
        """Fetch a single page of a specific category (or general listing)."""
        if cat_slug:
            url = f"https://www.sikayetvar.com/{self.brand_slug}/{cat_slug}?page={page}"
        else:
            url = f"https://www.sikayetvar.com/{self.brand_slug}?page={page}"

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                return []
            return _parse_page(resp.text, url, cat_name)
        except Exception as exc:
            logger.warning(
                "Şikayetvar (%s) page %d failed: %s", cat_name, page, exc,
            )
            return []

    def run_incremental(self, existing_hashes: set[str]) -> list[RawReview]:
        """Run incremental scrape across all categories independently.

        Each category is traversed from page 1 (newest) forward.
        When a known hash is found in a category, that category stops
        but others continue — new complaints may arrive in any category.
        """
        all_new: list[RawReview] = []

        # Build sources: general + all categories
        sources: list[tuple[str | None, str]] = [(None, "Genel")]
        sources.extend(SIKAYETVAR_CATEGORIES.items())

        for cat_slug, cat_name in sources:
            cat_new: list[RawReview] = []
            stop_cat = False

            for page in range(1, self.MAX_PAGES_PER_CATEGORY + 1):
                if stop_cat:
                    break

                page_reviews = self._fetch_category_page(cat_slug, cat_name, page)

                if not page_reviews:
                    break  # no more pages

                page_new = 0
                found_known = False
                for review in page_reviews:
                    h = text_hash(review.get("original_text", ""))
                    if h in existing_hashes:
                        found_known = True
                    else:
                        cat_new.append(review)
                        existing_hashes.add(h)
                        page_new += 1

                logger.info(
                    "Şikayetvar (%s) page %d: %d fetched, %d new, %d known.",
                    cat_name, page, len(page_reviews), page_new,
                    len(page_reviews) - page_new,
                )

                if found_known:
                    logger.info(
                        "Şikayetvar (%s): known hash found on page %d — "
                        "stopping this category.", cat_name, page,
                    )
                    stop_cat = True

                # Throttle
                if not stop_cat:
                    time.sleep(random.uniform(self.min_delay, self.max_delay))

            if cat_new:
                logger.info(
                    "Şikayetvar (%s): %d new reviews collected.", cat_name, len(cat_new),
                )
            all_new.extend(cat_new)

        logger.info(
            "[%s] Incremental scrape complete: %d new reviews across all categories.",
            self.platform_name, len(all_new),
        )
        return all_new
