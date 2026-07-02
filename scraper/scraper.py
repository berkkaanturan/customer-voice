"""
Scraper module for the Customer Voice Dashboard.

Provides functions to scrape customer reviews from:
  - Google Play Store
  - Apple App Store
  - Şikayetvar
  - Ekşi Sözlük

Şikayetvar and Ekşi Sözlük scrapers attempt real scraping but gracefully
fall back to realistic demo data when blocked or when HTML structure changes.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Type alias for a single review record ─────────────────────────────────────
ReviewRecord = dict[str, Any]

# ── Shared HTTP headers ───────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Google Play Store
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_play_store(app_id: str, count: int = 500) -> list[ReviewRecord]:
    """Scrape reviews from Google Play Store using google-play-scraper.

    Iterates over rating scores (1-5) and sorting modes (NEWEST, HELPFUL)
    to bypass the single-feed pagination limits, ensuring maximum historical
    retrieval.

    Args:
        app_id: The Android application package ID (e.g. "com.turknet.oim").
        count: Target number of reviews to fetch in total.

    Returns:
        List of review dicts with standardised keys.
    """
    try:
        from google_play_scraper import Sort, reviews as gp_reviews

        logger.info("Scraping Play Store for '%s' historically (target total=%d)…", app_id, count)
        reviews: list[ReviewRecord] = []

        scores = [1, 2, 3, 4, 5]
        sorts = [Sort.NEWEST, Sort.MOST_RELEVANT]
        combos = len(scores) * len(sorts)
        count_per_combo = max(50, count // combos)

        for score in scores:
            for sort_mode in sorts:
                try:
                    sort_name = "NEWEST" if sort_mode == Sort.NEWEST else "MOST_RELEVANT"
                    logger.info("Play Store: score=%d, sort=%s, count=%d...", score, sort_name, count_per_combo)
                    result, _ = gp_reviews(
                        app_id,
                        lang="tr",
                        country="tr",
                        sort=sort_mode,
                        count=count_per_combo,
                        filter_score_with=score,
                    )
                    if not result:
                        continue

                    for r in result:
                        reviews.append(
                            {
                                "platform_name": "Play Store",
                                "author": r.get("userName", "Anonim"),
                                "original_text": r.get("content", ""),
                                "rating": r.get("score"),
                                "source_url": f"https://play.google.com/store/apps/details?id={app_id}",
                                "scraped_at": (
                                    r["at"].replace(tzinfo=timezone.utc).isoformat() if isinstance(r.get("at"), datetime) else datetime.now(tz=timezone.utc).isoformat()
                                ),
                            }
                        )
                except Exception as exc:
                    logger.error("Play Store combo (score=%d, sort=%s) failed: %s", score, sort_mode, exc)

        logger.info("Play Store: fetched %d reviews total.", len(reviews))
        return reviews

    except Exception as exc:
        logger.error("Play Store scraping failed: %s", exc, exc_info=True)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# Apple App Store
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_app_store(app_name: str, country: str = "tr", count: int = 100, app_id: int | None = 1001052556) -> list[ReviewRecord]:
    """Scrape reviews from Apple App Store RSS feed directly (bypasses broken app-store-scraper)."""
    logger.info("Scraping App Store via RSS for app_id=%s...", app_id)
    reviews: list[ReviewRecord] = []
    
    # Apple RSS allows up to 10 pages, each page has 50 reviews.
    max_pages = min(10, (count + 49) // 50)
    
    for page in range(1, max_pages + 1):
        url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortBy=mostRecent/json"
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning("App Store RSS page %d returned status %d", page, resp.status_code)
                break
                
            data = resp.json()
            feed = data.get("feed", {})
            entries = feed.get("entry", [])
            
            # If entry is a single dict (can happen if only 1 review), wrap in list
            if isinstance(entries, dict):
                entries = [entries]
                
            if not entries:
                break
                
            for entry in entries:
                # The first entry in the RSS feed on page 1 is the app info metadata, skip it
                if "im:name" in entry:
                    continue
                    
                author = entry.get("author", {}).get("name", {}).get("label", "Anonim")
                content = entry.get("content", {}).get("label", "")
                title = entry.get("title", {}).get("label", "")
                rating_str = entry.get("im:rating", {}).get("label", "0")
                
                try:
                    rating = int(rating_str)
                except ValueError:
                    rating = None
                    
                # Full text is title + body
                full_text = f"{title}\n{content}" if title else content
                
                reviews.append({
                    "platform_name": "App Store",
                    "author": author,
                    "original_text": full_text.strip(),
                    "rating": rating,
                    "source_url": f"https://apps.apple.com/{country}/app/turknet/id{app_id}",
                    "scraped_at": entry.get("updated", {}).get("label") or datetime.now(tz=timezone.utc).isoformat(),
                })
                
                if len(reviews) >= count:
                    break
            
            if len(reviews) >= count:
                break
                
        except Exception as exc:
            logger.error("App Store RSS page %d failed: %s", page, exc)
            break
            
    logger.info("App Store RSS: fetched %d reviews.", len(reviews))
    return reviews


# ═══════════════════════════════════════════════════════════════════════════════
# Şikayetvar  (attempt real scraping → fall back to demo data)
# ═══════════════════════════════════════════════════════════════════════════════

_SIKAYETVAR_DEMO: list[dict[str, str]] = [
    {
        "author": "Ahmet Y.",
        "text": "TürkNet internet hızı sürekli düşüyor. 100 Mbps paketim var ama ölçümlerde en fazla 30 Mbps alıyorum. Teknik destek her seferinde 'altyapı yoğunluğu' diyor.",
    },
    {
        "author": "Fatma K.",
        "text": "Fiber geçiş sürecinde 2 hafta internetsiz kaldık. Kurulum ekibi randevuya gelmedi, defalarca aradım kimse bilgi vermedi.",
    },
    {
        "author": "Mehmet D.",
        "text": "Fatura tutarım her ay artıyor. Kampanya bitince fiyat neredeyse iki katına çıktı. Müşteri sadakati diye bir kavram yok.",
    },
    {
        "author": "Zeynep A.",
        "text": "Modem sürekli bağlantı koparıyor. Günde 5-6 kez reset atıyorum. Cihaz değişikliği talep ettim ama 'garanti kapsamında değil' dediler.",
    },
    {
        "author": "Can B.",
        "text": "Müşteri hizmetleri hattını aradığımda 45 dakika bekledim. Sonunda bağlandığımda sorunumu çözmeden başka birime yönlendirdiler.",
    },
    {
        "author": "Elif S.",
        "text": "TürkNet altyapı çalışması yapmış, 3 gündür internet yok. Hiçbir bilgilendirme yapılmadı, sosyal medyadan öğrendik.",
    },
    {
        "author": "Burak T.",
        "text": "Kurulum için gelen teknisyen kabloları düzgün çekmemiş. Bir hafta sonra bağlantı tamamen kesildi, tekrar gelmek zorunda kaldılar.",
    },
    {
        "author": "Selin Ö.",
        "text": "İnternet hızım gayet iyi, fiber geçişten sonra çok memnunum. Fiyat/performans açısından piyasadaki en iyi seçenek.",
    },
    {
        "author": "Hakan M.",
        "text": "Abonelik iptal sürecinde çok zorlandım. Online iptal seçeneği yok, müşteri hizmetlerini aramam gerekti ve beni vazgeçirmeye çalıştılar.",
    },
    {
        "author": "Ayşe R.",
        "text": "Fatura tarihim değiştirilmiş, habersizce ek ücret yansıtılmış. İtiraz ettiğimde 'sistem hatası' dediler ama düzeltmeleri 2 ay sürdü.",
    },
    {
        "author": "Emre K.",
        "text": "TürkNet'e geçeli 1 yıl oldu, genel olarak memnunum. Ara sıra akşam saatlerinde yavaşlama oluyor ama kabul edilebilir seviyede.",
    },
    {
        "author": "Deniz V.",
        "text": "Verdikleri modem çok kalitesiz, WiFi menzili çok kısa. Kendi modemimi takmak istedim ama 'desteklemiyoruz' dediler.",
    },
]

_EKSISOZLUK_DEMO: list[dict[str, str]] = [
    {
        "author": "sansen42",
        "text": "turknet'e geçtim, ilk ay her şey güzeldi. ikinci aydan itibaren akşam 8'den sonra internet kabuk hızına düşüyor. ping 150ms üstüne çıkıyor, oyun oynamak imkansız.",
    },
    {
        "author": "fiber_hayalcisi",
        "text": "turknet fiyat olarak en uygun seçenek ama altyapı yatırımı yapılmazsa bu avantaj uzun sürmez. müşteri çok hızlı artıyor, altyapı kaldırmıyor.",
    },
    {
        "author": "network_mansen",
        "text": "müşteri hizmetleri gerçekten iyi, bunu söylemek lazım. her aradığımda çözüm odaklı yaklaşıyorlar. diğer operatörlerden farklı bir deneyim.",
    },
    {
        "author": "kablosuz_derya",
        "text": "turknet modem değişimi için 200 lira ücret istedi. modem zaten onların, arızalı çalışıyor, neden ben ödeyeyim? saçmalık.",
    },
    {
        "author": "internetsansen",
        "text": "2 yıldır turknet kullanıyorum, fiyat artışları hariç şikayetim yok. her yıl yüzde 40-50 zam geliyor, bu böyle gitmez.",
    },
    {
        "author": "dijital_göçebe",
        "text": "evden çalışanlar için turknet fiber iyi bir seçenek. 50mbps paket alıyorum, gün içinde stabil çalışıyor. zoom toplantılarında sorun yaşamıyorum.",
    },
    {
        "author": "sansen_99",
        "text": "turknet kurulum randevusu aldım, teknisyen gelmedi. tekrar randevu verdiler, yine gelmedi. üçüncü denemede ancak gelebildiler. ciddi organizasyon sorunu var.",
    },
    {
        "author": "ankara_user",
        "text": "turknet altyapısı burada çok kötü. sürekli kopma yaşıyorum. arıza kaydı açıyorum ama çözülmüyor. superonline'a geri dönmeyi düşünüyorum.",
    },
    {
        "author": "tech_mehmet",
        "text": "turknet'in faturalama sistemi sorunlu. geçen ay kullanmadığım bir hizmet için ücret kesilmiş. itiraz süreci çok uzun ve yorucu.",
    },
    {
        "author": "happy_customer",
        "text": "turknet'ten gayet memnunum. 100mbps fiber kullanıyorum, hız testlerinde tam hız alıyorum. fiyatı da makul, tavsiye ederim.",
    },
]


def _parse_turkish_date(date_str: str | None) -> str:
    """Parse Turkish relative or absolute dates to ISO format, e.g. '22 Haziran 23:25'."""
    now = datetime.now(tz=timezone.utc)
    if not date_str:
        return now.isoformat()
    
    date_str = date_str.lower().strip()
    
    # Handle relative terms
    if "saat önce" in date_str or "saat once" in date_str:
        try:
            hours = int(date_str.split()[0])
            return (now - timedelta(hours=hours)).isoformat()
        except:
            pass
    elif "dakika önce" in date_str or "dakika once" in date_str:
        try:
            mins = int(date_str.split()[0])
            return (now - timedelta(minutes=mins)).isoformat()
        except:
            pass
    elif "dün" in date_str or "dun" in date_str:
        return (now - timedelta(days=1)).isoformat()
    
    # Months mapping
    months = {
        "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
        "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
        "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12
    }
    
    parts = date_str.split()
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            month_name = parts[1]
            month = months.get(month_name, 1)
            
            # Check if year is present
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
                        
            # Turkey is in UTC+3 timezone
            tr_tz = timezone(timedelta(hours=3))
            dt = datetime(year, month, day, hour, minute, tzinfo=tr_tz)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception as exc:
            logger.warning("Failed to parse Turkish date '%s': %s", date_str, exc)
            
    return now.isoformat()


def scrape_sikayetvar(brand_slug: str, page_count: int = 1, start_page: int = 1) -> list[ReviewRecord]:
    """Scrape complaints from Şikayetvar.

    Iterates over all 22 categories of complaints for the brand to get a much larger
    coverage of reviews, plus the main brand listing page.

    Args:
        brand_slug: Brand identifier on Şikayetvar (e.g. "turknet").
        page_count: Number of listing pages to fetch per category/listing.

    Returns:
        List of review dicts.
    """


    categories = {
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
        "yalin-internet": "Yalın İnternet"
    }

    reviews: list[ReviewRecord] = []

    # 1. First, scrape the general pages (catch-all)
    for page in range(start_page, start_page + page_count):
        url = f"https://www.sikayetvar.com/{brand_slug}?page={page}"
        try:
            logger.info("Şikayetvar (Genel): fetching page %d → %s", page, url)
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article") or soup.select(".complaint-card")
                for card in cards:
                    title_el = card.select_one("h3 a")
                    subject = title_el.get_text(strip=True) if title_el else ""
                    relative_url = title_el.get("href", "") if title_el else ""
                    source_url = f"https://www.sikayetvar.com{relative_url}" if relative_url else url
                    author_el = card.select_one("header span.font-bold")
                    author = author_el.get_text(strip=True) if author_el else "Anonim"
                    date_el = card.select_one("header span.text-zinc-500")
                    date_str = date_el.get_text(strip=True) if date_el else None
                    scraped_at = _parse_turkish_date(date_str)
                    text_el = card.select_one("p.wrap-anywhere") or card.select_one("p")
                    text = text_el.get_text(strip=True) if text_el else ""

                    if text:
                        reviews.append(
                            {
                                "platform_name": "Şikayetvar",
                                "author": author,
                                "original_text": text,
                                "rating": None,
                                "source_url": source_url,
                                "subject": subject,
                                "category": "Genel",  # classified later
                                "scraped_at": scraped_at,
                            }
                        )
            time.sleep(random.uniform(2.0, 5.0))
        except Exception as exc:
            logger.warning("Şikayetvar general page %d failed: %s", page, exc)

    # 2. Scrape category-specific pages
    for cat_slug, cat_name in categories.items():
        for page in range(start_page, start_page + page_count):
            url = f"https://www.sikayetvar.com/{brand_slug}/{cat_slug}?page={page}"
            try:
                logger.info("Şikayetvar (%s): fetching page %d → %s", cat_name, page, url)
                resp = requests.get(url, headers=_HEADERS, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article") or soup.select(".complaint-card")
                if not cards:
                    break

                scraped_count = 0
                for card in cards:
                    title_el = card.select_one("h3 a")
                    subject = title_el.get_text(strip=True) if title_el else ""
                    relative_url = title_el.get("href", "") if title_el else ""
                    source_url = f"https://www.sikayetvar.com{relative_url}" if relative_url else url
                    author_el = card.select_one("header span.font-bold")
                    author = author_el.get_text(strip=True) if author_el else "Anonim"
                    date_el = card.select_one("header span.text-zinc-500")
                    date_str = date_el.get_text(strip=True) if date_el else None
                    scraped_at = _parse_turkish_date(date_str)
                    text_el = card.select_one("p.wrap-anywhere") or card.select_one("p")
                    text = text_el.get_text(strip=True) if text_el else ""

                    if text:
                        reviews.append(
                            {
                                "platform_name": "Şikayetvar",
                                "author": author,
                                "original_text": text,
                                "rating": None,
                                "source_url": source_url,
                                "subject": subject,
                                "category": cat_name,  # pre-classified
                                "scraped_at": scraped_at,
                            }
                        )
                        scraped_count += 1
                logger.info("Şikayetvar (%s) page %d: scraped %d complaints.", cat_name, page, scraped_count)
                time.sleep(random.uniform(2.0, 5.0))
            except Exception as exc:
                logger.warning("Şikayetvar (%s) page %d failed: %s", cat_name, page, exc)
                break

    logger.info("Şikayetvar: total %d reviews scraped.", len(reviews))
    return reviews


# ═══════════════════════════════════════════════════════════════════════════════
# Ekşi Sözlük  (attempt real scraping → fall back to demo data)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_eksi_date(date_str: str | None) -> str:
    """Parse Ekşi Sözlük entry date string to ISO format, fallback to now."""
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    if not date_str:
        return now_iso
    try:
        original_date = date_str.split("~")[0].strip()
        try:
            dt = datetime.strptime(original_date, "%d.%m.%Y %H:%M")
        except ValueError:
            dt = datetime.strptime(original_date, "%d.%m.%Y")
        # Turkey is in UTC+3 timezone
        tr_tz = timezone(timedelta(hours=3))
        dt = dt.replace(tzinfo=tr_tz)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception as exc:
        logger.warning("Failed to parse Ekşi Sözlük date '%s': %s", date_str, exc)
        return now_iso


def discover_eksi_topics(keywords: str = "turknet", limit: int = 10) -> list[str]:
    """Search Ekşi Sözlük for threads containing the keywords and return their slugs."""
    # We query both date-sorted results (to fetch new 2026/recent threads) and default relevance results
    urls = [
        f"https://eksisozluk.com/basliklar/ara?searchform.keywords={keywords}&searchform.sortorder=date",
        f"https://eksisozluk.com/basliklar/ara?searchform.keywords={keywords}"
    ]
    
    topics = []
    
    for url in urls:
        try:
            logger.info("Ekşi Sözlük: searching for topics matching '%s' via → %s", keywords, url)
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning("Ekşi Sözlük search page failed with status %d", resp.status_code)
                continue
                
            # Check if redirected directly to a topic page (e.g. eksisozluk.com/turknet--244793)
            current_url = resp.url
            if "eksisozluk.com/" in current_url:
                path = current_url.split("eksisozluk.com/")[-1].split("?")[0]
                if "--" in path:
                    slug = path.lstrip("/")
                    logger.info("Ekşi Sözlük: redirected directly to topic '%s'", slug)
                    if slug not in topics:
                        topics.append(slug)
                    continue

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=True)
            
            for a in links:
                href = a["href"]
                if "--" in href and keywords in href.lower() and href.startswith("/"):
                    slug = href.lstrip("/")
                    if slug not in topics:
                        topics.append(slug)
        except Exception as exc:
            logger.error("Failed to fetch Ekşi Sözlük search url %s: %s", url, exc)

    if not topics:
        return [keywords]

    logger.info("Ekşi Sözlük: discovered %d unique topics matching '%s'.", len(topics), keywords)
    return topics[:limit]


def scrape_eksisozluk(topic: str, page_count: int | None = None) -> list[ReviewRecord]:
    """Scrape entries from Ekşi Sözlük.

    Resolves the final redirected URL, checks the total page count, and scrapes the
    latest pages (containing the newest 2026 comments) instead of the oldest first page.

    Args:
        topic: The başlık (topic/title) to scrape.
        page_count: Number of pages to fetch.

    Returns:
        List of review dicts.
    """
    reviews: list[ReviewRecord] = []

    # 1. Resolve redirect and find total page count
    initial_url = f"https://eksisozluk.com/{topic}"
    try:
        logger.info("Ekşi Sözlük: resolving initial topic url → %s", initial_url)
        resp = requests.get(initial_url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning("Ekşi Sözlük: topic '%s' returned status %d", topic, resp.status_code)
            return []

        # Get final redirected path
        current_url = resp.url
        resolved_topic = current_url.split("eksisozluk.com/")[-1].split("?")[0].lstrip("/")
        if not resolved_topic:
            resolved_topic = topic

        # Parse page count
        soup = BeautifulSoup(resp.text, "html.parser")
        pager = soup.select_one(".pager")
        total_pages = 1
        if pager:
            try:
                total_pages = int(pager.get("data-pagecount") or 1)
            except ValueError:
                pass

        logger.info("Ekşi Sözlük: resolved topic to '%s' with %d total pages.", resolved_topic, total_pages)

        # Determine which pages to scrape: if page_count is None, scrape all pages;
        # otherwise, scrape the last 'page_count' pages.
        if page_count is None:
            pages_to_scrape = list(range(1, total_pages + 1))
        else:
            pages_to_scrape = []
            for i in range(page_count):
                p = total_pages - i
                if p >= 1:
                    pages_to_scrape.append(p)
            pages_to_scrape.reverse()

        for page in pages_to_scrape:
            url = f"https://eksisozluk.com/{resolved_topic}?p={page}"
            try:
                logger.info("Ekşi Sözlük: fetching page %d → %s", page, url)
                page_resp = requests.get(url, headers=_HEADERS, timeout=15)
                if page_resp.status_code == 404:
                    continue
                page_resp.raise_for_status()

                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                title_el = page_soup.select_one("#title")
                if title_el:
                    topic_title = title_el.get("data-title", title_el.get_text(strip=True))
                else:
                    topic_title = resolved_topic.replace("-", " ").title()

                entries = page_soup.select("#entry-item-list > li") or page_soup.select("ul#entry-item-list li[data-id]")
                if not entries:
                    continue

                scraped_count = 0
                for entry in entries:
                    content_el = entry.select_one("div.content")
                    text = content_el.get_text(strip=True) if content_el else ""
                    author_el = entry.select_one("a.entry-author")
                    author = author_el.get_text(strip=True) if author_el else "Anonim"
                    date_el = entry.select_one("a.entry-date")
                    date_str = date_el.get_text(strip=True) if date_el else None
                    entry_id = entry.get("data-id", "")
                    entry_url = f"https://eksisozluk.com/entry/{entry_id}" if entry_id else url

                    if text:
                        reviews.append(
                            {
                                "platform_name": "Ekşi Sözlük",
                                "author": author,
                                "original_text": text,
                                "rating": None,
                                "source_url": entry_url,
                                "subject": topic_title,
                                "scraped_at": _parse_eksi_date(date_str),
                            }
                        )
                        scraped_count += 1
                logger.info("Ekşi Sözlük page %d: scraped %d entries.", page, scraped_count)
                time.sleep(random.uniform(2.0, 5.0))
            except Exception as e:
                logger.warning("Ekşi Sözlük: failed to fetch page %d: %s", page, e)

    except Exception as e:
        logger.error("Ekşi Sözlük: failed to resolve topic '%s': %s", topic, e)

    return reviews


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _build_demo_reviews(
    demos: list[dict[str, str]],
    platform: str,
    base_url: str,
) -> list[ReviewRecord]:
    """Convert raw demo entries into standardised ReviewRecord dicts.

    Assigns random dates within the last 30 days so the demo data looks
    realistic in the dashboard.
    """
    now = datetime.now(tz=timezone.utc)
    reviews: list[ReviewRecord] = []

    for demo in demos:
        random_days = random.randint(0, 30)
        random_hours = random.randint(0, 23)
        review_dt = now - timedelta(days=random_days, hours=random_hours)

        reviews.append(
            {
                "platform_name": platform,
                "author": demo["author"],
                "original_text": demo["text"],
                "rating": None,
                "source_url": base_url,
                "subject": "Demo Konu Başlığı",
                "scraped_at": review_dt.isoformat(),
            }
        )

    return reviews
