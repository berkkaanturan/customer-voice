"""
Configuration module for the Customer Voice Dashboard scraper.

Loads environment variables from .env file and exports them as constants.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this file
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

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
