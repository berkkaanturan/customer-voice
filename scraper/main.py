#!/usr/bin/env python3
"""
Customer Voice Dashboard — main pipeline orchestrator.

Usage:
    python main.py            # Run the full scrape → analyse → save pipeline
    python main.py --seed     # Seed the database with ~50 realistic demo reviews
"""

from __future__ import annotations

import argparse
import logging
import random
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from analyzer import analyze_review
from config import (
    APP_STORE_APP_NAME,
    APP_STORE_COUNTRY,
    CATEGORIES,
    EKSISOZLUK_TOPIC,
    PLAY_STORE_APP_ID,
    SENTIMENTS,
    SIKAYETVAR_BRAND,
)
from db import save_reviews
from scraper import (
    discover_eksi_topics,
    scrape_app_store,
    scrape_eksisozluk,
    scrape_play_store,
    scrape_sikayetvar,
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


# ═══════════════════════════════════════════════════════════════════════════════
# State Management for Backfill
# ═══════════════════════════════════════════════════════════════════════════════
STATE_FILE = "state.json"

def load_state() -> dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load state.json: %s", e)
    return {
        "sikayetvar_page": 6,
        "play_store_count": 3500
    }

def save_state(state: dict[str, Any]) -> None:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning("Failed to save state.json: %s", e)

# ═══════════════════════════════════════════════════════════════════════════════
# Full pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(cron_mode: bool = False, backfill_mode: bool = False) -> None:
    """Execute the full scrape → analyse → save pipeline for all platforms."""
    start = time.monotonic()
    logger.info("=" * 60)
    logger.info("Customer Voice Pipeline — starting")
    logger.info("=" * 60)

    # ── Step 1: Scrape all platforms ──────────────────────────────────────────
    all_reviews: list[dict[str, Any]] = []

    logger.info("── Step 1/3: Scraping all platforms ──")

    if backfill_mode:
        logger.info("BACKFILL MODE: Continuing from previous state to fetch historical data.")
        state = load_state()
        play_count = state["play_store_count"]
        appstore_count = 500  # Max limit
        sikayetvar_pages = 5
        sv_start_page = state["sikayetvar_page"]
        eksi_pages = None # Just fetch all for backfill
    elif cron_mode:
        logger.info("CRON MODE: Running lightweight incremental scrape.")
        play_count = 100
        appstore_count = 50
        sikayetvar_pages = 2
        sv_start_page = 1
        eksi_pages = 2
    else:
        play_count = 3000
        appstore_count = 500
        sikayetvar_pages = 5
        sv_start_page = 1
        eksi_pages = None

    play_reviews = scrape_play_store(PLAY_STORE_APP_ID, count=play_count)
    all_reviews.extend(play_reviews)
    logger.info("Play Store: %d reviews", len(play_reviews))

    appstore_reviews = scrape_app_store(
        APP_STORE_APP_NAME, country=APP_STORE_COUNTRY, count=appstore_count
    )
    all_reviews.extend(appstore_reviews)
    logger.info("App Store: %d reviews", len(appstore_reviews))

    sikayetvar_reviews = scrape_sikayetvar(SIKAYETVAR_BRAND, page_count=sikayetvar_pages, start_page=sv_start_page)
    all_reviews.extend(sikayetvar_reviews)
    logger.info("Şikayetvar: %d reviews (from page %d)", len(sikayetvar_reviews), sv_start_page)

    eksi_topics = discover_eksi_topics("turknet", limit=35)
    for topic in eksi_topics:
        logger.info("Ekşi Sözlük: fetching topic '%s'…", topic)
        eksi_reviews = scrape_eksisozluk(topic, page_count=eksi_pages)
        all_reviews.extend(eksi_reviews)
        logger.info("Ekşi Sözlük ('%s'): %d reviews", topic, len(eksi_reviews))

    logger.info("Total scraped: %d reviews across all platforms.", len(all_reviews))

    if not all_reviews:
        logger.warning("No reviews scraped. Exiting pipeline.")
        return

    # ── Step 2: Analyse each review with rule-based system ────────────────────
    logger.info("── Step 2/3: Analysing reviews with rule-based system ──")
    total = len(all_reviews)

    for idx, review in enumerate(all_reviews, start=1):
        text = review.get("original_text", "")
        rating = review.get("rating")
        result = analyze_review(text, rating=rating)
        review["sentiment"] = result["sentiment"]
        review["category"] = result["category"]

        if idx % 10 == 0 or idx == total:
            logger.info("Analysed %d / %d reviews.", idx, total)

    # ── Step 3: Save to Supabase ─────────────────────────────────────────────
    logger.info("── Step 3/3: Saving to Supabase ──")
    inserted = save_reviews(all_reviews)

    # ── Step 4: Update State (if backfill) ───────────────────────────────────
    if backfill_mode:
        state["sikayetvar_page"] += sikayetvar_pages
        state["play_store_count"] += 500
        save_state(state)
        logger.info("Updated backfill state: %s", state)

    elapsed = time.monotonic() - start
    logger.info("=" * 60)
    logger.info(
        "Pipeline complete — %d scraped, %d inserted, %.1fs elapsed.",
        len(all_reviews),
        inserted,
        elapsed,
    )
    logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# Demo data seeder
# ═══════════════════════════════════════════════════════════════════════════════

# Realistic Turkish telecom customer reviews for seeding
_SEED_REVIEWS: list[dict[str, Any]] = [
    # ── Negative — Altyapı ────────────────────────────────────────────────────
    {"text": "Mahallemizde altyapı çalışması yapıldı ama internet daha da kötüleşti. Fiber hat çekilecek denildi, 6 aydır bekliyoruz.", "sentiment": "Negative", "category": "Altyapı", "platform": "Şikayetvar", "rating": None},
    {"text": "Altyapı eski bakır kablo, fiber geçiş tarihi sürekli erteleniyor. Komşu mahallede fiber var bizde hâlâ ADSL.", "sentiment": "Negative", "category": "Altyapı", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "Yağmur yağdığında internet kesiliyor. Altyapı sorunlu ama kimse ilgilenmiyor. 3 kez arıza kaydı açtırdım.", "sentiment": "Negative", "category": "Altyapı", "platform": "Şikayetvar", "rating": None},

    # ── Negative — Fiyat ──────────────────────────────────────────────────────
    {"text": "Kampanya bitince fiyat 250 TL'den 480 TL'ye çıktı. Hiçbir bilgilendirme yapılmadı. Bu kabul edilemez!", "sentiment": "Negative", "category": "Fiyat", "platform": "Play Store", "rating": 1},
    {"text": "Her 3 ayda bir zam geliyor. Başlangıçta ucuz diye geldim ama artık diğer operatörlerden farkı kalmadı.", "sentiment": "Negative", "category": "Fiyat", "platform": "App Store", "rating": 2},
    {"text": "Taahhüt bitince fiyat uçtu, sadakat indirimi yok. Yeni müşteriye verilen kampanyayı bize vermiyorlar.", "sentiment": "Negative", "category": "Fiyat", "platform": "Şikayetvar", "rating": None},

    # ── Negative — Kurulum ────────────────────────────────────────────────────
    {"text": "Kurulum randevusu 3 kez ertelendi. Sonunda gelen teknisyen de işini bilmiyordu, kabloları yanlış bağladı.", "sentiment": "Negative", "category": "Kurulum", "platform": "Şikayetvar", "rating": None},
    {"text": "Fiber kurulum için başvurduk, 3 hafta oldu hâlâ haber yok. Her aradığımda 'en kısa sürede' diyorlar.", "sentiment": "Negative", "category": "Kurulum", "platform": "Play Store", "rating": 1},
    {"text": "Teknisyen geldi ama gerekli malzeme yokmuş. Tekrar gelecekmiş, 5 gündür bekliyorum.", "sentiment": "Negative", "category": "Kurulum", "platform": "Ekşi Sözlük", "rating": None},

    # ── Negative — Müşteri Hizmetleri ─────────────────────────────────────────
    {"text": "Müşteri hizmetlerini her aradığımda en az 30 dakika bekliyorum. Bağlandığımda da sorunumu çözmüyorlar.", "sentiment": "Negative", "category": "Müşteri Hizmetleri", "platform": "Play Store", "rating": 1},
    {"text": "Chat desteği bot gibi çalışıyor, gerçek bir insanla konuşmak imkansız. Her seferinde aynı kalıp cevaplar.", "sentiment": "Negative", "category": "Müşteri Hizmetleri", "platform": "App Store", "rating": 1},
    {"text": "Sosyal medyadan yazdım, 2 gün sonra cevap geldi. O da 'DM'den ulaşın' oldu. DM'den de cevap yok.", "sentiment": "Negative", "category": "Müşteri Hizmetleri", "platform": "Şikayetvar", "rating": None},

    # ── Negative — Fatura ─────────────────────────────────────────────────────
    {"text": "Faturama tanımadığım bir ek hizmet bedeli eklenmiş. İtiraz ettim, 'siz onaylamışsınız' dediler. Onaylamadım!", "sentiment": "Negative", "category": "Fatura", "platform": "Şikayetvar", "rating": None},
    {"text": "İptal ettiğim halde 2 ay daha fatura geldi. İade süreci çok uzun ve zahmetli.", "sentiment": "Negative", "category": "Fatura", "platform": "Play Store", "rating": 1},
    {"text": "Fatura tutarı her ay farklı. Sabit paket alıyorum ama fatura sabit değil. Şeffaflık sıfır.", "sentiment": "Negative", "category": "Fatura", "platform": "App Store", "rating": 2},

    # ── Negative — Hız ────────────────────────────────────────────────────────
    {"text": "100 Mbps paketim var ama akşam saatlerinde 5 Mbps bile zor alıyorum. YouTube bile donuyor.", "sentiment": "Negative", "category": "Hız", "platform": "Play Store", "rating": 1},
    {"text": "Hız testi yapıyorum, taahhüt edilen hızın yarısını bile almıyorum. Akşam 7'den sonra kullanılamaz durumda.", "sentiment": "Negative", "category": "Hız", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "Fiber 50 Mbps paket aldım ama indirme hızı 15 Mbps'yi geçmiyor. Oyun indirmek işkence.", "sentiment": "Negative", "category": "Hız", "platform": "App Store", "rating": 1},
    {"text": "Upload hızı çok düşük, evden çalışırken video konferans yapmak imkansız. Sürekli donma yaşıyorum.", "sentiment": "Negative", "category": "Hız", "platform": "Şikayetvar", "rating": None},

    # ── Negative — Modem/Cihaz ────────────────────────────────────────────────
    {"text": "Verdikleri modem çöp, WiFi sinyali bir odayı bile karşılamıyor. Kendi modemimi kullanmama izin vermiyorlar.", "sentiment": "Negative", "category": "Modem/Cihaz", "platform": "Play Store", "rating": 1},
    {"text": "Modem her gece 3-4 kez resetleniyor. Uyku modunda bile kopuyor. Cihaz değişimi talep ettim, 'stokta yok' dediler.", "sentiment": "Negative", "category": "Modem/Cihaz", "platform": "Şikayetvar", "rating": None},
    {"text": "Router'ın firmware'i güncellenmiyor, güvenlik açığı var. Teknik destek 'biz müdahale edemiyoruz' diyor.", "sentiment": "Negative", "category": "Modem/Cihaz", "platform": "Ekşi Sözlük", "rating": None},

    # ── Positive — Hız ────────────────────────────────────────────────────────
    {"text": "Fiber geçişten sonra internet süper hızlı. 100 Mbps alıyorum, hız testinde de taahhüt edilen rakamı görüyorum.", "sentiment": "Positive", "category": "Hız", "platform": "Play Store", "rating": 5},
    {"text": "TürkNet fiber gerçekten çok iyi. Ping değerlerim mükemmel, online oyunlarda hiç lag yaşamıyorum.", "sentiment": "Positive", "category": "Hız", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "200 Mbps fiber kullanıyorum, gece gündüz aynı hız. Çok memnunum, kesinlikle tavsiye ederim.", "sentiment": "Positive", "category": "Hız", "platform": "App Store", "rating": 5},

    # ── Positive — Fiyat ──────────────────────────────────────────────────────
    {"text": "Fiyat/performans olarak piyasadaki en iyi seçenek TürkNet. Aynı hızı başka yerde bu fiyata bulamazsınız.", "sentiment": "Positive", "category": "Fiyat", "platform": "Play Store", "rating": 5},
    {"text": "Ucuz ve kaliteli internet arayan herkese TürkNet'i öneriyorum. 2 yıldır kullanıyorum, memnunum.", "sentiment": "Positive", "category": "Fiyat", "platform": "App Store", "rating": 4},

    # ── Positive — Müşteri Hizmetleri ─────────────────────────────────────────
    {"text": "Müşteri hizmetleri çok ilgili. Sorunumu ilk aramada çözdüler, diğer operatörlerden çok farklı.", "sentiment": "Positive", "category": "Müşteri Hizmetleri", "platform": "Play Store", "rating": 5},
    {"text": "Twitter'dan yazdım, 10 dakika içinde dönüş yaptılar. Sorunu aynı gün çözdüler. Bravo!", "sentiment": "Positive", "category": "Müşteri Hizmetleri", "platform": "App Store", "rating": 5},
    {"text": "Çağrı merkezi personeli gerçekten yardımcı oluyor. Sabırlı ve çözüm odaklı. Teşekkürler TürkNet.", "sentiment": "Positive", "category": "Müşteri Hizmetleri", "platform": "Şikayetvar", "rating": None},

    # ── Positive — Kurulum ────────────────────────────────────────────────────
    {"text": "Fiber kurulum çok hızlı oldu. Başvurumdan 2 gün sonra teknisyen geldi, 1 saatte her şey hazırdı.", "sentiment": "Positive", "category": "Kurulum", "platform": "Play Store", "rating": 5},
    {"text": "Kurulum ekibi çok profesyoneldi. Kabloları düzgün çektiler, her şeyi test edip gittiler.", "sentiment": "Positive", "category": "Kurulum", "platform": "Ekşi Sözlük", "rating": None},

    # ── Positive — Genel ──────────────────────────────────────────────────────
    {"text": "3 yıldır TürkNet müşterisiyim, genel olarak çok memnunum. Ara sıra küçük aksaklıklar oluyor ama hızlı çözülüyor.", "sentiment": "Positive", "category": "Genel", "platform": "Play Store", "rating": 4},
    {"text": "TürkNet'e geçmek en doğru kararımdı. Hem ucuz hem kaliteli. Ailecek mutluyuz.", "sentiment": "Positive", "category": "Genel", "platform": "App Store", "rating": 5},

    # ── Neutral ───────────────────────────────────────────────────────────────
    {"text": "TürkNet ortalama bir servis sunuyor. Ne çok iyi ne çok kötü. Fiyatı makul, hız idare eder.", "sentiment": "Neutral", "category": "Genel", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "Bir yıldır TürkNet kullanıyorum. Büyük sorun yaşamadım ama etkileyici bir şey de yok. Normal.", "sentiment": "Neutral", "category": "Genel", "platform": "Play Store", "rating": 3},
    {"text": "Hızlar fena değil ama mükemmel de değil. Fiyatı uygun olduğu için devam ediyorum.", "sentiment": "Neutral", "category": "Hız", "platform": "App Store", "rating": 3},
    {"text": "Modem fena değil aslında, WiFi menzili ortalama. Çok büyük evlerde sorun olabilir ama bizim ev için yeterli.", "sentiment": "Neutral", "category": "Modem/Cihaz", "platform": "Play Store", "rating": 3},
    {"text": "Fatura sistemi karışık ama sorduğunuzda açıklıyorlar. Online işlemler biraz geliştirilmeli.", "sentiment": "Neutral", "category": "Fatura", "platform": "App Store", "rating": 3},
    {"text": "Altyapı çalışması sırasında 1 gün internet kesildi ama önceden bilgilendirdiler. Kabul edilebilir.", "sentiment": "Neutral", "category": "Altyapı", "platform": "Ekşi Sözlük", "rating": None},
    {"text": "Kurulum süreci normal sürdü, 1 hafta içinde bağlandık. Hızlı değildi ama çok da yavaş değildi.", "sentiment": "Neutral", "category": "Kurulum", "platform": "Şikayetvar", "rating": None},

    # ── A few more negatives for realism (heavier negative skew) ──────────────
    {"text": "İnternet 2 gündür yok. Arıza kaydı açtırdım ama tahmini çözüm süresi bile verilmedi.", "sentiment": "Negative", "category": "Altyapı", "platform": "Şikayetvar", "rating": None},
    {"text": "Cayma bedeli çok yüksek. 24 ay taahhüt verdim ama hizmet bu kadar kötüyken devam etmek zor.", "sentiment": "Negative", "category": "Fiyat", "platform": "Play Store", "rating": 1},
    {"text": "Uygulama sürekli çöküyor, fatura bilgilerime ulaşamıyorum. Çok kötü bir uygulama.", "sentiment": "Negative", "category": "Genel", "platform": "Play Store", "rating": 1},
    {"text": "Gece yarısı internet hızı 1 Mbps'ye düşüyor. Netflix izlemek imkansız. Çok hayal kırıklığı.", "sentiment": "Negative", "category": "Hız", "platform": "App Store", "rating": 1},
]

# Author pool for seeding
_SEED_AUTHORS: list[str] = [
    "Ahmet Y.", "Fatma K.", "Mehmet D.", "Zeynep A.", "Can B.",
    "Elif S.", "Burak T.", "Selin Ö.", "Hakan M.", "Ayşe R.",
    "Emre K.", "Deniz V.", "Merve Ç.", "Oğuz H.", "Gizem N.",
    "Ali P.", "Ecem T.", "Barış U.", "Nur G.", "Serkan L.",
    "Pınar F.", "Murat İ.", "Ceren B.", "Uğur S.", "Damla E.",
]


def seed_demo_data() -> None:
    """Insert ~50 realistic demo reviews with pre-assigned sentiments and categories.

    Dates are spread randomly over the last 30 days so the dashboard charts
    look realistic from day one.
    """
    logger.info("=" * 60)
    logger.info("Seeding demo data…")
    logger.info("=" * 60)

    now = datetime.now(tz=timezone.utc)
    reviews: list[dict[str, Any]] = []

    for seed in _SEED_REVIEWS:
        random_days = random.randint(0, 30)
        random_hours = random.randint(0, 23)
        random_mins = random.randint(0, 59)
        review_dt = now - timedelta(
            days=random_days, hours=random_hours, minutes=random_mins
        )

        reviews.append(
            {
                "platform_name": seed["platform"],
                "author": random.choice(_SEED_AUTHORS),
                "original_text": seed["text"],
                "sentiment": seed["sentiment"],
                "category": seed["category"],
                "rating": seed.get("rating"),
                "source_url": _platform_url(seed["platform"]),
                "scraped_at": review_dt.isoformat(),
            }
        )

    inserted = save_reviews(reviews)

    # Print summary
    sentiments = {}
    categories = {}
    platforms = {}
    for r in reviews:
        sentiments[r["sentiment"]] = sentiments.get(r["sentiment"], 0) + 1
        categories[r["category"]] = categories.get(r["category"], 0) + 1
        platforms[r["platform_name"]] = platforms.get(r["platform_name"], 0) + 1

    logger.info("── Seed summary ──")
    logger.info("Total reviews: %d (inserted: %d)", len(reviews), inserted)
    logger.info("Sentiments: %s", sentiments)
    logger.info("Categories: %s", categories)
    logger.info("Platforms:  %s", platforms)
    logger.info("=" * 60)


def _platform_url(platform: str) -> str:
    """Return a representative source URL for a platform name."""
    urls = {
        "Play Store": f"https://play.google.com/store/apps/details?id={PLAY_STORE_APP_ID}",
        "App Store": f"https://apps.apple.com/{APP_STORE_COUNTRY}/app/{APP_STORE_APP_NAME}",
        "Şikayetvar": f"https://www.sikayetvar.com/{SIKAYETVAR_BRAND}",
        "Ekşi Sözlük": f"https://eksisozluk.com/{EKSISOZLUK_TOPIC}",
    }
    return urls.get(platform, "")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate function."""
    parser = argparse.ArgumentParser(
        description="Customer Voice Dashboard — scraper pipeline",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with ~50 realistic demo reviews instead of scraping.",
    )
    parser.add_argument(
        "--cron",
        action="store_true",
        help="Run in lightweight cron mode (less pages/history).",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run in backfill mode to fetch historical data iteratively.",
    )
    args = parser.parse_args()

    if args.seed:
        seed_demo_data()
    else:
        run_pipeline(cron_mode=args.cron, backfill_mode=args.backfill)


if __name__ == "__main__":
    main()
