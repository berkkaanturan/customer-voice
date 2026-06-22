"""
Rule-based analyzer for the Customer Voice Dashboard.

Classifies customer reviews by sentiment and category using keyword matching
and rating indicators. Completely offline and bypasses Gemini API to eliminate
rate limits and network delays.
"""

from __future__ import annotations

import logging
from typing import Any

from config import CATEGORIES, SENTIMENTS

logger = logging.getLogger(__name__)

# ── Keyword definitions for category classification ─────────────────────────
CATEGORIES_KEYWORDS: dict[str, list[str]] = {
    "Abonelik": [
        "abone", "abonelik", "iptal", "başvuru", "basvuru", "sözleşme", "sozlesme",
        "evrak", "kimlik", "taahhüt", "taahhut", "kampanya", "imza"
    ],
    "Adres Değişikliği": [
        "adres", "nakil", "taşınma", "tasinma", "adres değişikliği", "adres degisikligi",
        "yeni ev", "ev taşıma", "tasindik", "nakli"
    ],
    "ADSL": [
        "adsl", "bakır kablo", "bakir kablo", "bakır altyapı", "16 mbps", "16mbps"
    ],
    "Altyapı": [
        "altyapı", "altyapi", "kablo", "bina", "sokak", "mahalle", "kutusu", "port yok",
        "port", "ankastre", "gpon", "altyapısı", "altyapisi"
    ],
    "Altyapısız İnternet": [
        "altyapısız", "altyapisiz", "altyapı yok", "altyapi yok", "şebeke yok"
    ],
    "Arıza": [
        "arıza", "ariza", "bozuk", "çalışmıyor", "calismiyor", "problem", "teknik",
        "ekip bekliyoruz", "arıza kaydı", "ariza kaydi", "teknisyen"
    ],
    "Bakım Çalışması": [
        "bakım", "bakim", "çalışma", "calisma", "planlı kesinti", "planli kesinti",
        "çalışması var", "iyileştirme", "iyilestirme"
    ],
    "Dondurma İşlemi": [
        "dondurma", "dondurmak", "askıya", "askiya", "geçici iptal", "dondurdum"
    ],
    "Ev Telefonu Hizmeti": [
        "ev telefonu", "sabit hat", "sabit telefon", "yalın telefon", "ev tel"
    ],
    "Evde İnternet": [
        "ev interneti", "evde internet", "ev internet", "wifi ev", "ev modemi"
    ],
    "Fatura": [
        "fatura", "ödeme", "odeme", "ücret", "ucret", "tutar", "para", "kart",
        "tahsilat", "tl", "faturası", "faturasi", "cayma", "iade", "kesilmiş",
        "yansıtılmış", "zam", "pahalı"
    ],
    "Fiber İnternet": [
        "fiber", "gpon", "fiber optik", "100 mbps", "1000 mbps", "fiber altyapı"
    ],
    "Gezgin İnternet": [
        "gezgin", "yazlık internet", "yazlik internet", "yazlık", "gezginnet"
    ],
    "Gigafiber": [
        "gigafiber", "giga", "1000 mbps", "simetrik", "gigafiber altyapı"
    ],
    "Hız Testi": [
        "hız testi", "hiz testi", "speedtest", "hızım düştü", "hizim dustu",
        "fast.com", "hız ölçüm", "hiz olcum"
    ],
    "İnternet Kesintisi": [
        "kesildi", "kesinti", "internet yok", "bağlantı koptu", "baglanti koptu",
        "kopuyor", "sinyal yok", "los ışığı", "los isigi", "kırmızı yanıyor", "gitti"
    ],
    "İnternet Paketleri": [
        "paket", "tarife", "hız paketi", "kotasız", "kotasiz", "paketler"
    ],
    "Modem": [
        "modem", "router", "wifi", "kablosuz", "sinyal", "çekim gücü", "cekim gucu",
        "zyxel", "keenetic", "tp-link", "kanal", "wlan"
    ],
    "Online İşlemler": [
        "online işlemler", "online islemler", "oim", "uygulama", "app", "mobil uygulama",
        "şifre", "sifre", "giriş yapamıyorum", "giriş", "giris", "oim şifre"
    ],
    "Ping Sorunu": [
        "ping", "lag", "ms", "oyun", "loss", "gecikme", "packet loss", "pubg", "csgo", "valorant"
    ],
    "VDSL": [
        "vdsl", "35 mbps", "75 mbps", "hipernet", "hiper net", "35mbps", "75mbps"
    ],
    "Yalın İnternet": [
        "yalın internet", "yalin internet", "telefonsuz", "yalınnet"
    ]
}

# ── Sentiment analysis keywords ──────────────────────────────────────────────
POSITIVE_KEYWORDS = [
    "iyi", "harika", "süper", "super", "mükemmel", "mukemmel", "hızlı", "hizli",
    "memnun", "tavsiye", "teşekkür", "tesekkur", "başarılı", "basarili", "stabil",
    "kesintisiz", "sorunsuz", "bravo", "kaliteli", "hızlıca", "memnunum", "güzel",
    "guzel", "hızlı", "beğendim", "begendim"
]

NEGATIVE_KEYWORDS = [
    "kötü", "kotu", "rezalet", "berbat", "yavaş", "yavas", "donuyor", "çöp", "cop",
    "kopuyor", "şikayet", "sikayet", "hüsran", "husran", "yazık", "yazik", "sinir",
    "bıktım", "biktim", "mağdur", "magdur", "rezillik", "ilgilenmiyor", "gelmedi",
    "çözülmedi", "cozulmedi", "iptal", "lanet", "hata", "bozuk", "pahalı", "pahali",
    "zam", "bekliyoruz", "pişman", "pisman", "nefret", "bıktık", "biktik",
    "memnun değil", "memnun degil", "iyi değil", "iyi degil", "hızlı değil",
    "hizli degil", "çalışmıyor", "calismiyor"
]


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_review(text: str, rating: int | None = None, max_retries: int = 3) -> dict[str, str]:
    """Analyse a single review text using rules and keyword matching.

    Args:
        text: The raw review/complaint text.
        rating: Optional platform rating (1-5), used as primary sentiment indicator.
        max_retries: Kept for backwards compatibility but unused.

    Returns:
        Dict with "sentiment" and "category" keys.
    """
    if not text or not text.strip():
        return {"sentiment": "Neutral", "category": "Genel"}

    text_lower = text.lower()

    # 1. Classify Category based on keyword counts
    category_scores = {cat: 0 for cat in CATEGORIES_KEYWORDS.keys()}

    for category, keywords in CATEGORIES_KEYWORDS.items():
        for kw in keywords:
            # Add weight based on word occurrences
            category_scores[category] += text_lower.count(kw)

    # Find category with highest match score
    best_category = "Genel"
    max_score = 0
    for cat, score in category_scores.items():
        if score > max_score:
            max_score = score
            best_category = cat

    # 2. Determine Sentiment
    # Use rating if available (most reliable indicator)
    if rating is not None:
        if rating >= 4:
            sentiment = "Positive"
        elif rating <= 2:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
    else:
        # Fallback to keyword-based score
        pos_score = sum(text_lower.count(kw) for kw in POSITIVE_KEYWORDS)
        neg_score = sum(text_lower.count(kw) for kw in NEGATIVE_KEYWORDS)

        if neg_score > pos_score:
            sentiment = "Negative"
        elif pos_score > neg_score:
            sentiment = "Positive"
        else:
            sentiment = "Neutral"

    return {"sentiment": sentiment, "category": best_category}


def analyze_reviews_batch(
    reviews: list[dict[str, Any]],
    delay: float = 0.0,
) -> list[dict[str, Any]]:
    """Analyse a batch of reviews, adding sentiment & category to each.

    Modifies each review dict **in place** and also returns the list.
    """
    total = len(reviews)
    logger.info("Starting rule-based analysis for %d reviews…", total)

    for idx, review in enumerate(reviews, start=1):
        text = review.get("original_text", "")
        rating = review.get("rating")
        result = analyze_review(text, rating=rating)
        review["sentiment"] = result["sentiment"]
        review["category"] = result["category"]

        if idx % 10 == 0 or idx == total:
            logger.info("Analysed %d / %d reviews.", idx, total)

    logger.info("Rule-based analysis complete.")
    return reviews
