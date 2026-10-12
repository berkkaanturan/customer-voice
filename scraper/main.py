#!/usr/bin/env python3
"""
Customer Voice Dashboard — pipeline orchestrator (v2).

Usage:
    python main.py                     # Incremental scrape → analyse → save
    python main.py --dry-run           # Scrape & analyse without saving to DB
    python main.py --backfill          # Backfill history (default: last 30 days)
    python main.py --backfill --since 2026-09-01  # Backfill from specific date
    python main.py --platform eksi     # Run single platform (eksi, sikayetvar, play, app)
    python main.py --seed              # Seed ~50 demo reviews
    python main.py --clear             # Delete all records from reviews table
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from analyzer import analyze_review
from base_scraper import RawReview, ScrapeContext, parse_iso
from config import (
    APP_STORE_APP_NAME,
    APP_STORE_COUNTRY,
    CATEGORIES,
    INITIAL_LOOKBACK_DAYS,
    OVERLAP_PAGES,
    PLAY_STORE_APP_ID,
    SENTIMENTS,
    SIKAYETVAR_BRAND,
)
from db import (
    clear_all_reviews,
    get_known_ids,
    get_legacy_hashes,
    get_recent_logs,
    get_scrape_state,
    save_reviews,
    save_scrape_state,
    save_scraper_log,
)

from adapters import (
    AppStoreAdapter,
    EksiSozlukAdapter,
    PlayStoreAdapter,
    SikayetvarAdapter,
)

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")


# ── Alerting helper ───────────────────────────────────────────────────────────
def send_alert_if_needed(summary: dict[str, Any]) -> None:
    """Best-effort notification via webhook or Telegram if configured."""
    alerts: list[str] = []

    # 1. Platform failure
    for p_name, stats in summary.get("platform_stats", {}).items():
        if stats.get("errors"):
            alerts.append(f"⚠️ {p_name} error: {stats['errors'][:2]}")

    # 2. Şikayetvar 403
    sv_stats = summary.get("platform_stats", {}).get("Şikayetvar", {})
    if sv_stats.get("blocked", 0) > 0:
        alerts.append(f"🚨 Şikayetvar received {sv_stats['blocked']} blocked responses (403/429).")

    # 3. Two consecutive zero-review runs
    recent = get_recent_logs(limit=2)
    if len(recent) >= 2:
        for p_name in ["Ekşi Sözlük", "Şikayetvar"]:
            zeroes = all(
                (log.get("platform_stats", {}).get(p_name, {}).get("new_reviews") == 0)
                for log in recent
            )
            curr_zero = summary.get("platform_stats", {}).get(p_name, {}).get("new_reviews") == 0
            if zeroes and curr_zero:
                alerts.append(f"ℹ️ {p_name}: 0 new reviews for 3 consecutive runs.")

    if not alerts:
        return

    msg = "Customer Voice Alert:\n" + "\n".join(alerts)
    logger.warning("ALERTS TRIGGERED:\n%s", msg)

    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            import requests
            requests.post(webhook_url, json={"text": msg}, timeout=10)
        except Exception as exc:
            logger.warning("Failed to send webhook alert: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Execution
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    *,
    dry_run: bool = False,
    backfill_since: datetime | None = None,
    target_platforms: list[str] | None = None,
) -> None:
    start = time.monotonic()
    mode = "BACKFILL" if backfill_since else ("DRY-RUN" if dry_run else "INCREMENTAL")
    logger.info("=" * 60)
    logger.info("Customer Voice Pipeline — starting (%s mode)", mode)
    if backfill_since:
        logger.info("Backfill cutoff date: %s", backfill_since.isoformat())
    logger.info("=" * 60)

    start_time_iso = datetime.now(timezone.utc).isoformat()
    platform_stats: dict[str, Any] = {}
    overall_status = "success"
    overall_error: str | None = None

    try:
        # ── Step 1: Load Context from DB ──────────────────────────────────────
        logger.info("── Step 1/4: Loading state & known IDs from DB ──")
        known_ids = get_known_ids()
        legacy_hashes = get_legacy_hashes()
        state = get_scrape_state()

        ctx = ScrapeContext(
            known_ids=known_ids,
            legacy_hashes=legacy_hashes,
            state=state,
            backfill_since=backfill_since,
            initial_lookback_days=INITIAL_LOOKBACK_DAYS,
            overlap_pages=OVERLAP_PAGES,
        )

        # ── Step 2: Initialize & Run Adapters ─────────────────────────────────
        logger.info("── Step 2/4: Running scrapers ──")
        all_adapters = [
            ("play", PlayStoreAdapter(app_id=PLAY_STORE_APP_ID)),
            ("app", AppStoreAdapter(app_id=1001052556, country=APP_STORE_COUNTRY)),
            ("sikayetvar", SikayetvarAdapter(brand_slug=SIKAYETVAR_BRAND)),
            ("eksi", EksiSozlukAdapter()),
        ]

        active_adapters = []
        for alias, adapter in all_adapters:
            if target_platforms and alias not in target_platforms and adapter.platform_name.lower() not in target_platforms:
                continue
            active_adapters.append(adapter)

        all_new_reviews: list[RawReview] = []

        for adapter in active_adapters:
            logger.info("── Scraping %s ──", adapter.platform_name)
            a_start = time.monotonic()
            try:
                new_revs = adapter.run_incremental(ctx)
                elapsed = time.monotonic() - a_start
                all_new_reviews.extend(new_revs)
                logger.info(
                    "%s: %d new reviews found in %.1fs.",
                    adapter.platform_name, len(new_revs), elapsed,
                )
                stats = dict(adapter.stats)
                stats.update({
                    "new_reviews": len(new_revs),
                    "duration_seconds": round(elapsed, 2),
                })
                platform_stats[adapter.platform_name] = stats
            except Exception as exc:
                elapsed = time.monotonic() - a_start
                logger.error("%s adapter crashed: %s", adapter.platform_name, exc, exc_info=True)
                platform_stats[adapter.platform_name] = {
                    "new_reviews": 0,
                    "duration_seconds": round(elapsed, 2),
                    "error": str(exc),
                }

        logger.info("Total new reviews collected: %d", len(all_new_reviews))

        # ── Step 3: Analyze ───────────────────────────────────────────────────
        if all_new_reviews:
            logger.info("── Step 3/4: Analysing reviews ──")
            total = len(all_new_reviews)
            for idx, review in enumerate(all_new_reviews, start=1):
                text = review.get("original_text", "")
                rating = review.get("rating")
                res = analyze_review(text, rating=rating)
                review["sentiment"] = res["sentiment"]
                if not review.get("category"):
                    review["category"] = res["category"]
                review["keywords"] = res.get("keywords", [])
                if idx % 100 == 0 or idx == total:
                    logger.info("Analysed %d / %d reviews.", idx, total)

        # ── Step 4: Save ──────────────────────────────────────────────────────
        inserted = 0
        failed = 0
        if not dry_run:
            logger.info("── Step 4/4: Persisting reviews & watermark state ──")
            if all_new_reviews:
                inserted, failed = save_reviews(all_new_reviews)
            save_scrape_state(list(ctx.state_updates.values()))
        else:
            logger.info("DRY-RUN: Skipping database persistence.")
            inserted = len(all_new_reviews)

        elapsed = time.monotonic() - start
        logger.info("=" * 60)
        logger.info(
            "Pipeline finished — %d collected, %d saved (%d failed), %.1fs elapsed.",
            len(all_new_reviews), inserted, failed, elapsed,
        )
        logger.info("=" * 60)

    except Exception as exc:
        overall_status = "error"
        overall_error = str(exc)
        logger.error("Pipeline failed fatally: %s", exc, exc_info=True)

    finally:
        total_duration = time.monotonic() - start
        end_time_iso = datetime.now(timezone.utc).isoformat()
        log_payload = {
            "started_at": start_time_iso,
            "completed_at": end_time_iso,
            "total_duration_seconds": round(total_duration, 2),
            "status": overall_status,
            "error_message": overall_error,
            "platform_stats": platform_stats,
        }
        if not dry_run:
            try:
                save_scraper_log(log_payload)
            except Exception as e:
                logger.warning("Failed to save scraper log: %s", e)
            send_alert_if_needed(log_payload)


# ═══════════════════════════════════════════════════════════════════════════════
# Demo Seeder & CLI
# ═══════════════════════════════════════════════════════════════════════════════

_SEED_REVIEWS: list[dict[str, Any]] = [
    {"text": "Mahallemizde altyapı çalışması yapıldı ama internet daha da kötüleşti. Fiber hat çekilecek denildi, 6 aydır bekliyoruz.", "sentiment": "Negative", "category": "Altyapı", "platform": "Şikayetvar", "rating": None},
    {"text": "Altyapı eski bakır kablo, fiber geçiş tarihi sürekli erteleniyor. Komşu mahallede fiber var bizde hâlâ ADSL.", "sentiment": "Negative", "category": "Altyapı", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "Kampanya bitince fiyat 250 TL'den 480 TL'ye çıktı. Hiçbir bilgilendirme yapılmadı. Bu kabul edilemez!", "sentiment": "Negative", "category": "Fiyat", "platform": "Play Store", "rating": 1},
    {"text": "Fiber geçişten sonra internet süper hızlı. 100 Mbps alıyorum, taahhüt edilen rakamı görüyorum.", "sentiment": "Positive", "category": "Hız", "platform": "Play Store", "rating": 5},
    {"text": "TürkNet fiber gerçekten çok iyi. Ping değerlerim mükemmel, online oyunlarda hiç lag yaşamıyorum.", "sentiment": "Positive", "category": "Hız", "platform": "Ekşi Sözlük", "rating": None},
]

def seed_demo_data() -> None:
    logger.info("Seeding demo data…")
    now = datetime.now(tz=timezone.utc)
    reviews: list[dict[str, Any]] = []
    for i, s in enumerate(_SEED_REVIEWS, start=1):
        reviews.append({
            "platform_name": s["platform"],
            "external_id": f"seed-{i}",
            "author": "Demo Kullanıcı",
            "original_text": s["text"],
            "sentiment": s["sentiment"],
            "category": s["category"],
            "rating": s.get("rating"),
            "source_url": "https://turk.net",
            "scraped_at": (now - timedelta(days=i)).isoformat(),
        })
    inserted, _ = save_reviews(reviews)
    logger.info("Seeded %d demo reviews.", inserted)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Customer Voice Dashboard — incremental scraper pipeline v2",
    )
    parser.add_argument("--seed", action="store_true", help="Seed demo reviews")
    parser.add_argument("--clear", action="store_true", help="Delete all records from reviews")
    parser.add_argument("--dry-run", action="store_true", help="Scrape & analyze without DB writes")
    parser.add_argument("--backfill", action="store_true", help="Backfill historical reviews past the known watermark")
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Cutoff date for backfill in YYYY-MM-DD format (defaults to 30 days ago if --backfill is passed)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help="Run specific platform(s), comma-separated: eksi,sikayetvar,play,app",
    )
    args = parser.parse_args()

    if args.clear:
        clear_all_reviews()
        return

    if args.seed:
        seed_demo_data()
        return

    backfill_since = None
    if args.backfill:
        if args.since:
            try:
                backfill_since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error("Invalid --since format. Use YYYY-MM-DD (e.g. 2026-09-01).")
                sys.exit(1)
        else:
            backfill_since = datetime.now(timezone.utc) - timedelta(days=30)

    target_platforms = [p.strip().lower() for p in args.platform.split(",")] if args.platform else None

    run_pipeline(
        dry_run=args.dry_run,
        backfill_since=backfill_since,
        target_platforms=target_platforms,
    )


if __name__ == "__main__":
    main()
