"""
Play Store adapter (v2 — paginated incremental).

Uses google-play-scraper with Sort.NEWEST and continuation_token to walk
backwards in time until reaching known review IDs or the date cutoff.
Every review has a permanent, unique ``reviewId``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from base_scraper import IncrementalScraper, RawReview, ScrapeContext, parse_iso

logger = logging.getLogger(__name__)


class PlayStoreAdapter(IncrementalScraper):
    platform_name = "Play Store"

    def __init__(self, app_id: str = "com.turknet.oim", batch_size: int = 150, max_reviews: int = 4000) -> None:
        super().__init__()
        self.app_id = app_id
        self.batch_size = batch_size
        self.max_reviews = max_reviews

    def run_incremental(self, ctx: ScrapeContext) -> list[RawReview]:
        try:
            from google_play_scraper import Sort, reviews as gp_reviews
        except ImportError:
            logger.error("google-play-scraper is not installed.")
            return []

        source_key = "default"
        cutoff = ctx.cutoff_for(self.platform_name, source_key)
        backfill = ctx.backfill_since is not None

        new_reviews: list[RawReview] = []
        token: Any = None
        total_fetched = 0
        exhausted_streak = 0
        newest_dt: datetime | None = None
        newest_id: str | None = None
        errors: list[str] = []

        logger.info(
            "Play Store: starting crawl (app=%s, cutoff=%s, backfill=%s)…",
            self.app_id, cutoff, backfill,
        )

        while total_fetched < self.max_reviews:
            try:
                batch, token = gp_reviews(
                    self.app_id,
                    lang="tr",
                    country="tr",
                    sort=Sort.NEWEST,
                    count=self.batch_size,
                    continuation_token=token,
                )
            except Exception as exc:
                logger.error("Play Store: batch failed: %s", exc, exc_info=True)
                errors.append(str(exc))
                break

            if not batch:
                logger.info("Play Store: empty batch received — end of reviews.")
                break

            total_fetched += len(batch)
            batch_new = 0
            batch_old = 0

            for r in batch:
                ext_id = str(r.get("reviewId") or "").strip()
                dt: datetime | None = r.get("at")
                if isinstance(dt, datetime):
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = None

                if dt and (newest_dt is None or dt > newest_dt):
                    newest_dt = dt
                    newest_id = ext_id or newest_id

                if cutoff and dt and dt < cutoff:
                    batch_old += 1
                    continue

                review: RawReview = {
                    "platform_name": self.platform_name,
                    "external_id": ext_id,
                    "author": r.get("userName") or "Anonim",
                    "original_text": r.get("content") or "",
                    "rating": r.get("score"),
                    "source_url": f"https://play.google.com/store/apps/details?id={self.app_id}",
                    "scraped_at": dt.isoformat() if dt else datetime.now(timezone.utc).isoformat(),
                    "subject": None,
                    "category": None,
                }

                if not review["original_text"]:
                    continue

                if ctx.is_known(review):
                    continue

                ctx.mark_seen(review)
                new_reviews.append(review)
                batch_new += 1

            known = len(batch) - batch_new - batch_old
            logger.info(
                "Play Store batch: %d fetched, %d new, %d known, %d older than cutoff.",
                len(batch), batch_new, known, batch_old,
            )

            if backfill:
                exhausted = batch_old == len(batch)
            else:
                exhausted = batch_new == 0

            if batch_old == len(batch):
                logger.info("Play Store: whole batch older than cutoff — stopping.")
                break

            exhausted_streak = exhausted_streak + 1 if exhausted else 0
            if exhausted_streak > ctx.overlap_pages:
                logger.info("Play Store: %d consecutive exhausted batches — stopping.", exhausted_streak)
                break

            if not token:
                logger.info("Play Store: no continuation token returned — end of stream.")
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
            ctx.update_state(self.platform_name, source_key)

        self.stats = {
            "total_fetched": total_fetched,
            "new_reviews": len(new_reviews),
            "errors": errors,
        }
        logger.info("[Play Store] %d new reviews collected out of %d fetched.", len(new_reviews), total_fetched)
        return new_reviews
