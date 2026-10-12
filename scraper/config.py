"""
Configuration module for the Customer Voice Dashboard scraper.

Loads environment variables from .env file and exports them as constants.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from the same directory as this file
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "")

# ── Gemini AI ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Play Store ────────────────────────────────────────────────────────────────
PLAY_STORE_APP_ID: str = os.getenv("PLAY_STORE_APP_ID", "com.turknet.oim")

# ── App Store ─────────────────────────────────────────────────────────────────
APP_STORE_APP_NAME: str = os.getenv("APP_STORE_APP_NAME", "turknet")
APP_STORE_COUNTRY: str = os.getenv("APP_STORE_COUNTRY", "tr")

# ── Şikayetvar ────────────────────────────────────────────────────────────────
SIKAYETVAR_BRAND: str = os.getenv("SIKAYETVAR_BRAND", "turknet")

# ── Ekşi Sözlük ──────────────────────────────────────────────────────────────
EKSISOZLUK_TOPIC: str = os.getenv("EKSISOZLUK_TOPIC", "turknet")
EKSISOZLUK_TOPICS: list[str] = [
    "turknet",
    "turknet-rezaleti",
    "turknet-yavasligi",
    "turknet-rezilligi",
    "turknet-online-islemler"
]
# All search phrases used for topic discovery (every result page is read).
EKSI_SEARCH_KEYWORDS: list[str] = ["turknet", "türknet", "turk net", "türk net"]
# Topics scanned on every run regardless of discovery / change detection.
# The main "türk net" topic is where most daily entries are written.
EKSI_PINNED_TOPICS: list[str] = ["turk-net--912228"]
# A discovered slug must match this to be considered TürkNet-related.
EKSI_TOPIC_PATTERN: str = r"(^|-)t[uü]rk-?net[a-z0-9]{0,4}(-|$)"
# Re-scan a topic even if its entry count didn't change after this many days
# (catches "one deleted + one added" cases).
EKSI_FULL_RESCAN_DAYS: int = int(os.getenv("EKSI_FULL_RESCAN_DAYS", "7"))

# ── Incremental scraping ─────────────────────────────────────────────────────
# For a source that has never been scraped, how far back to go on a normal run.
INITIAL_LOOKBACK_DAYS: int = int(os.getenv("INITIAL_LOOKBACK_DAYS", "180"))
# Extra fully-known pages to scan before stopping (safety overlap).
OVERLAP_PAGES: int = int(os.getenv("OVERLAP_PAGES", "1"))

# ── Gemini Model ──────────────────────────────────────────────────────────────
GEMINI_MODEL: str = "gemini-2.5-flash"

# ── Review categories (Turkish) ──────────────────────────────────────────────
CATEGORIES: list[str] = [
    "Abonelik",
    "Adres Değişikliği",
    "ADSL",
    "Altyapı",
    "Altyapısız İnternet",
    "Arıza",
    "Bakım Çalışması",
    "Dondurma İşlemi",
    "Ev Telefonu Hizmeti",
    "Evde İnternet",
    "Fatura",
    "Fiber İnternet",
    "Gezgin İnternet",
    "Gigafiber",
    "Hız Testi",
    "İnternet Kesintisi",
    "İnternet Paketleri",
    "Modem",
    "Online İşlemler",
    "Ping Sorunu",
    "VDSL",
    "Yalın İnternet",
    "Genel",
]

# ── Sentiments ────────────────────────────────────────────────────────────────
SENTIMENTS: list[str] = ["Positive", "Negative", "Neutral"]

# ── HTTP Headers & User Agent Rotation ────────────────────────────────────────
import random

USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    # Chrome on Android
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    # Safari on iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/605.1.15"
]

def get_random_headers() -> dict[str, str]:
    """Generate realistic random HTTP headers to bypass CDN/WAF blocking."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Connection": "keep-alive"
    }
