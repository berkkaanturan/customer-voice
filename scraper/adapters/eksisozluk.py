"""
Ekşi Sözlük adapter (v2).

* Discovery: every result page of every phrase in ``EKSI_SEARCH_KEYWORDS`` is
  read (≈190+ topics), plus ``EKSI_PINNED_TOPICS`` (the main "türk net" topic).
* Change detection: the search page shows each topic's entry count.  A topic
  is only crawled when its count grew since the last run (pinned topics, new
  topics, backfill runs and topics not checked for ``EKSI_FULL_RESCAN_DAYS``
  are always crawled).  This keeps the daily request count low.
* Crawl: Ekşi pages are oldest → newest, so we walk from the last page
  backwards with the shared ID-watermark engine (entry ``data-id``).
* Each topic is isolated: one failing topic never discards the others.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from base_scraper import IncrementalScraper, RawReview, ScrapeContext, parse_iso
from config import (
    EKSI_FULL_RESCAN_DAYS,
    EKSI_PINNED_TOPICS,
    EKSI_SEARCH_KEYWORDS,
    EKSI_TOPIC_PATTERN,
)
from http_client import BlockedError, HttpClient

logger = logging.getLogger(__name__)

BASE = "https://eksisozluk.com"

# ── Topic blacklist — slugs containing these substrings will be skipped ──────
BLACKLISTED_SLUGS: set[str] = {
    "top-sakal",
}

_TOPIC_RE = re.compile(EKSI_TOPIC_PATTERN)


def _is_blacklisted(slug: str) -> bool:
    """Check if a topic slug matches any blacklist entry."""
    slug_lower = slug.lower()
    return any(bl in slug_lower for bl in BLACKLISTED_SLUGS)


def _topic_id(slug: str) -> str:
    """'turk-net--912228' → '912228' (stable even if the title/slug changes)."""
    return slug.rsplit("--", 1)[-1] if "--" in slug else slug


def _parse_eksi_date(date_str: str | None) -> str:
    """Parse Ekşi Sözlük entry date string to ISO format (UTC)."""
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


class EksiSozlukAdapter(IncrementalScraper):
    platform_name = "Ekşi Sözlük"

    def __init__(self) -> None:
        super().__init__()
        self.http = HttpClient(
            "Ekşi Sözlük", min_delay=1.5, max_delay=3.5, retries=3,
            backoff_base=10, warmup_url=BASE + "/", proxy_env="EKSI_PROXY_URL",
        )

    # ── discovery ─────────────────────────────────────────────────────────
    def discover_topics(self) -> dict[str, dict]:
        """Return {topic_id: {"slug", "title", "count"}} for all TürkNet topics."""
        topics: dict[str, dict] = {}
        for kw in EKSI_SEARCH_KEYWORDS:
            for page in range(1, 50):
                url = f"{BASE}/basliklar/ara?searchform.keywords={quote_plus(kw)}&p={page}"
                resp = self.http.get(url, referer=BASE + "/")
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("ul.topic-list a[href]")
                added = 0
                for a in links:
                    slug = a["href"].split("?")[0].lstrip("/")
                    if "--" not in slug:
                        continue
                    name_part = slug.rsplit("--", 1)[0].lower()
                    if not _TOPIC_RE.search(name_part) or _is_blacklisted(slug):
                        continue
                    small = a.find("small")
                    count = None
                    if small:
                        try:
                            count = int(small.get_text(strip=True).replace(".", ""))
                        except ValueError:
                            count = None
                        small.extract()
                    tid = _topic_id(slug)
                    if tid not in topics:
                        added += 1
                    topics[tid] = {
                        "slug": slug,
                        "title": a.get_text(" ", strip=True),
                        "count": count if count is not None else 1,
                    }
                if not links:
                    break
                logger.info("Ekşi search %r page %d: %d links, %d new topics.", kw, page, len(links), added)
        logger.info("Ekşi: discovered %d TürkNet topics.", len(topics))
        return topics

    # ── single topic crawl ────────────────────────────────────────────────
    def _parse_entries(self, html: str, title_fallback: str) -> tuple[list[RawReview], str, int]:
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.select_one("#title")
        title = (title_el.get("data-title") if title_el else None) or title_fallback
        pager = soup.select_one(".pager")
        try:
            total_pages = int(pager.get("data-pagecount") or 1) if pager else 1
        except ValueError:
            total_pages = 1

        reviews: list[RawReview] = []
        for entry in soup.select("#entry-item-list > li[data-id]"):
            content_el = entry.select_one("div.content")
            text = content_el.get_text(" ", strip=True) if content_el else ""
            if not text:
                continue
            entry_id = entry.get("data-id", "")
            author = entry.get("data-author") or (
                entry.select_one("a.entry-author").get_text(strip=True)
                if entry.select_one("a.entry-author") else "Anonim"
            )
            date_el = entry.select_one("a.entry-date")
            reviews.append(RawReview(
                platform_name=self.platform_name,
                external_id=str(entry_id),
                author=author,
                original_text=text,
                rating=None,
                source_url=f"{BASE}/entry/{entry_id}",
                subject=title,
                scraped_at=_parse_eksi_date(date_el.get_text(strip=True) if date_el else None),
            ))
        return reviews, title, total_pages

    def crawl_topic(self, ctx: ScrapeContext, tid: str, info: dict) -> list[RawReview]:
        slug = info["slug"]
        first = self.http.get(f"{BASE}/{slug}", referer=BASE + "/")
        if first.status_code == 404:
            logger.info("Ekşi: topic %s not found (404) — skipping.", slug)
            return []
        resolved = first.url.split("eksisozluk.com/")[-1].split("?")[0].lstrip("/") or slug
        first_reviews, title, total_pages = self._parse_entries(first.text, info.get("title", slug))
        if not first_reviews:
            raise Exception(f"Topic '{slug}' returned no entries (CAPTCHA or HTML change?)")
        info["title"] = title

        cache = {1: first_reviews}

        def fetch(page: int) -> list[RawReview]:
            if page in cache:
                return cache[page]
            resp = self.http.get(f"{BASE}/{resolved}?p={page}", referer=f"{BASE}/{resolved}")
            if resp.status_code == 404:
                return []
            return self._parse_entries(resp.text, title)[0]

        new = self.scan_pages(
            ctx, tid, range(total_pages, 0, -1), fetch,
            label=f"Ekşi/{resolved} ({total_pages}p)",
        )
        ctx.update_state(
            self.platform_name, tid,
            last_entry_count=info.get("count"),
            meta={"slug": resolved, "title": title, "pages": total_pages},
        )
        return new

    # ── orchestration ─────────────────────────────────────────────────────
    def _needs_crawl(self, ctx: ScrapeContext, tid: str, info: dict, pinned: bool) -> str | None:
        if pinned:
            return "pinned"
        if ctx.backfill_since:
            return "backfill"
        state = ctx.get_state(self.platform_name, tid)
        if state is None:
            return "new topic"
        prev = state.get("last_entry_count")
        if prev is None or (info.get("count") or 0) > prev:
            return f"count {prev}→{info.get('count')}"
        updated = parse_iso(state.get("updated_at"))
        if updated is None or datetime.now(timezone.utc) - updated > timedelta(days=EKSI_FULL_RESCAN_DAYS):
            return "periodic rescan"
        return None

    def run_incremental(self, ctx: ScrapeContext) -> list[RawReview]:
        errors: list[str] = []
        try:
            topics = self.discover_topics()
        except Exception as exc:
            logger.error("Ekşi: topic discovery failed: %s — falling back to pinned + known topics.", exc)
            errors.append(f"discovery: {exc}")
            topics = {}
            for (platform, key), st in ctx.state.items():
                if platform == self.platform_name and (st.get("meta") or {}).get("slug"):
                    topics[key] = {"slug": st["meta"]["slug"], "title": st["meta"].get("title", ""), "count": None}

        pinned_ids = set()
        for slug in EKSI_PINNED_TOPICS:
            tid = _topic_id(slug)
            pinned_ids.add(tid)
            topics.setdefault(tid, {"slug": slug, "title": slug, "count": None})

        # Pinned first, then by entry count (busiest topics first)
        order = sorted(topics.items(), key=lambda kv: (kv[0] not in pinned_ids, -(kv[1].get("count") or 0)))

        all_new: list[RawReview] = []
        crawled = skipped = 0
        consecutive_blocks = 0
        for tid, info in order:
            reason = self._needs_crawl(ctx, tid, info, tid in pinned_ids)
            if not reason:
                skipped += 1
                continue
            logger.info("Ekşi: crawling '%s' (%s).", info["slug"], reason)
            try:
                new = self.crawl_topic(ctx, tid, info)
                all_new.extend(new)
                crawled += 1
                consecutive_blocks = 0
                if new:
                    logger.info("Ekşi ('%s'): %d new entries.", info["slug"], len(new))
            except BlockedError as exc:
                consecutive_blocks += 1
                errors.append(f"{info['slug']}: {exc}")
                logger.error("Ekşi: blocked on '%s': %s", info["slug"], exc)
                if consecutive_blocks >= 3:
                    errors.append("aborted after 3 consecutive blocked topics")
                    break
            except Exception as exc:
                errors.append(f"{info['slug']}: {exc}")
                logger.error("Ekşi: topic '%s' failed: %s", info["slug"], exc, exc_info=True)

        self.stats = {
            "topics_found": len(topics),
            "topics_crawled": crawled,
            "topics_skipped_unchanged": skipped,
            "requests": self.http.request_count,
            "blocked": self.http.blocked_count,
            "errors": errors,
        }
        logger.info(
            "[Ekşi Sözlük] %d new entries | %d topics found, %d crawled, %d unchanged, %d errors.",
            len(all_new), len(topics), crawled, skipped, len(errors),
        )
        return all_new
