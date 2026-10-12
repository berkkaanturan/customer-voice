"""
Şikayetvar adapter (v2 — resilient incremental).

Improvements over v1:
---------------------
* Primary source is the main brand listing (https://www.sikayetvar.com/turknet?page=N)
  which contains ALL complaints across all categories in newest-first order.
  Complaint cards already contain the category hashtag (e.g. "# Modem"), so we
  can read category tags directly from the card without crawling 22 extra sub-URLs.
  Daily request volume drops from ~50 requests to ~2–4 requests.
* Uses ``HttpClient`` with Chrome TLS impersonation (via ``curl_cffi``) and session
  warm-up on the home page.  Retries with backoff on 403/429 and supports an optional
  proxy via ``SIKAYETVAR_PROXY_URL``.
* Stable ``external_id`` derived from complaint path (e.g. ``turknet/<slug>``).
* Driven by the shared ``scan_pages`` engine (ID watermark + overlap stop rule).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from base_scraper import IncrementalScraper, RawReview, ScrapeContext
from http_client import BlockedError, HttpClient

logger = logging.getLogger(__name__)

BASE = "https://www.sikayetvar.com"


def _parse_turkish_date(date_str: str | None) -> str:
    """Parse Turkish relative or absolute dates to ISO format (UTC)."""
    now = datetime.now(tz=timezone.utc)
    if not date_str:
        return now.isoformat()

    cleaned = date_str.lower().strip()

    if "saat önce" in cleaned or "saat once" in cleaned:
        try:
            hours = int(cleaned.split()[0])
            return (now - timedelta(hours=hours)).isoformat()
        except Exception:
            pass
    elif "dakika önce" in cleaned or "dakika once" in cleaned:
        try:
            mins = int(cleaned.split()[0])
            return (now - timedelta(minutes=mins)).isoformat()
        except Exception:
            pass
    elif "dün" in cleaned or "dun" in cleaned:
        return (now - timedelta(days=1)).isoformat()

    months = {
        "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
        "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
        "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
        "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
    }

    parts = cleaned.split()
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


def _extract_category(card: BeautifulSoup) -> str:
    """Extract category tag if present on card, else fallback to Genel."""
    cat_link = card.select_one("a[data-ga-element='Collection_Name_Button']") or card.select_one("a[href*='/turknet/'][title]")
    if cat_link:
        text = cat_link.get_text(strip=True).lstrip("#").strip()
        if text:
            return text
    return "Genel"


class SikayetvarAdapter(IncrementalScraper):
    platform_name = "Şikayetvar"

    def __init__(self, brand_slug: str = "turknet", max_pages: int = 50) -> None:
        super().__init__()
        self.brand_slug = brand_slug
        self.max_pages = max_pages
        self.http = HttpClient(
            "Şikayetvar",
            min_delay=2.5,
            max_delay=5.0,
            retries=3,
            backoff_base=15.0,
            warmup_url=f"{BASE}/{brand_slug}",
            proxy_env="SIKAYETVAR_PROXY_URL",
        )

    def _parse_page(self, html: str) -> list[RawReview]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article") or soup.select(".complaint-card")
        reviews: list[RawReview] = []

        for card in cards:
            title_el = card.select_one("h3 a")
            subject = title_el.get_text(strip=True) if title_el else ""
            rel_href = title_el.get("href", "").strip() if title_el else ""
            if not rel_href:
                continue

            # e.g. /turknet/turknet-ev-interneti-surekli-kopuyor...
            clean_path = rel_href.split("?")[0].lstrip("/")
            external_id = clean_path
            source_url = f"{BASE}/{clean_path}"

            author_el = card.select_one("header span.font-bold") or card.select_one("span[aria-label]")
            author = author_el.get_text(strip=True) if author_el else "Anonim"

            # Prefer aria-label on time/date span for exact date (e.g. '13 Ekim 2026 00:01')
            date_el = (
                card.select_one("header span[aria-label*='20']")
                or card.select_one("header span.text-zinc-500")
            )
            date_str = None
            if date_el:
                date_str = date_el.get("aria-label") or date_el.get_text(strip=True)

            text_el = card.select_one("p.wrap-anywhere") or card.select_one("p")
            text = text_el.get_text(" ", strip=True) if text_el else ""

            if not text:
                continue

            category = _extract_category(card)

            reviews.append(
                RawReview(
                    platform_name=self.platform_name,
                    external_id=external_id,
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

    def run_incremental(self, ctx: ScrapeContext) -> list[RawReview]:
        """Scan the brand's main complaint feed page by page."""
        source_key = "genel"
        errors: list[str] = []

        def fetch(page: int) -> list[RawReview]:
            url = f"{BASE}/{self.brand_slug}?page={page}"
            referer = f"{BASE}/{self.brand_slug}" if page > 1 else BASE + "/"
            resp = self.http.get(url, referer=referer)
            if resp.status_code == 404:
                return []
            return self._parse_page(resp.text)

        all_new: list[RawReview] = []
        try:
            all_new = self.scan_pages(
                ctx,
                source_key,
                range(1, self.max_pages + 1),
                fetch,
                label=f"Şikayetvar/{self.brand_slug}",
                max_pages=self.max_pages,
            )
        except BlockedError as exc:
            logger.error("Şikayetvar: blocked (403/429): %s", exc)
            errors.append(str(exc))
        except Exception as exc:
            logger.error("Şikayetvar: scrape failed: %s", exc, exc_info=True)
            errors.append(str(exc))

        self.stats = {
            "requests": self.http.request_count,
            "blocked": self.http.blocked_count,
            "using_proxy": self.http.using_proxy,
            "new_reviews": len(all_new),
            "errors": errors,
        }
        return all_new
