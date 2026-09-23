import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import random
import re
import xml.etree.ElementTree as ET

DB_NAME = "ps2_market.db"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

POSITIVE_WORDS = ["pickup", "grail", "gem", "love", "worth", "collection", "found", "deal", "steal", "nostalgia", "cib"]
NEGATIVE_WORDS = ["overpriced", "expensive", "scam", "fake", "reseller", "damaged", "ruined", "skip", "worst", "loose"]

CURRENCY_RATES_TO_USD = {
    "USD": 1.0, "EUR": 1.09, "GBP": 1.28, "CAD": 0.74, "AUD": 0.67,
    "CHF": 1.15, "PLN": 0.25, "MXN": 0.052, "HKD": 0.13, "SGD": 0.76,
    "MYR": 0.23, "PHP": 0.018, "TWD": 0.031, "JPY": 0.0067
}

NEWS_FEEDS = [
    {"source": "IGN", "url": "https://feeds.feedburner.com/ign/all"},
    {"source": "Eurogamer", "url": "https://www.eurogamer.net/?format=rss"},
    {"source": "PushSquare", "url": "https://www.pushsquare.com/feeds/latest"}
]

NEWS_MATCH_KEYWORDS = [
    "ps2", "sony ps2", "playstation 2", "record sale", "auction", "heritage", "wata", "vga", 
    "sealed", "retro gaming", "vintage console"
]

EBAY_REGIONS = {
    "US": {"domain": "www.ebay.com", "currency": "USD"},
    "UK": {"domain": "www.ebay.co.uk", "currency": "GBP"},
    "DE": {"domain": "www.ebay.de", "currency": "EUR"},
    "CA": {"domain": "www.ebay.ca", "currency": "CAD"}
}

session = requests.Session()

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9"
    }

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_extended_tables():
    conn = get_db()
    cursor = conn.cursor()
    
    # Core tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE,
            region TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS record_sales_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            title TEXT,
            source TEXT,
            sale_price_usd REAL,
            listing_url TEXT,
            date_detected TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT,
            link TEXT,
            published_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            source TEXT,
            condition TEXT,
            price_amount REAL,
            volume_active INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            platform TEXT,
            post_count INTEGER,
            total_upvotes INTEGER,
            total_comments INTEGER,
            avg_sentiment REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_index (
            index_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            cib_weighted_price REAL,
            market_cap_contribution REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def scrape_retro_news():
    conn = get_db()
    cursor = conn.cursor()
    
    for feed in NEWS_FEEDS:
        try:
            res = session.get(feed["url"], headers=get_headers(), timeout=8)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "xml")
                for item in soup.find_all("item")[:15]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    
                    if title_elem and link_elem:
                        title_text = title_elem.text.strip()
                        link_text = link_elem.text.strip()
                        pub_date = pub_elem.text.strip() if pub_elem else ""
                        
                        if any(kw in title_text.lower() for kw in NEWS_MATCH_KEYWORDS):
                            cursor.execute("""
                                INSERT INTO news_articles (source, title, link, published_date)
                                VALUES (?, ?, ?, ?)
                            """, (feed["source"], title_text, link_text, pub_date))
        except Exception as e:
            continue
            
    conn.commit()
    conn.close()

def check_auction_record_sales(game_id, title):
    search_query = f"{title} playstation 2 sealed wata vga".replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={search_query}&LH_BIN=1"
    
    try:
        res = session.get(url, headers=get_headers(), timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for item in soup.select(".s-item"):
                price_elem = item.select_one(".s-item__price")
                link_elem = item.select_one("a.s-item__link")
                
                if price_elem and link_elem:
                    # Clean price string and handle price ranges
                    raw_text = price_elem.text.split("to")[0]
                    clean_price = re.sub(r"[^\d.]", "", raw_text.replace(",", ""))
                    try:
                        price_val = float(clean_price)
                        if price_val >= 5000.0:
                            conn = get_db()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO record_sales_alerts (game_id, title, source, sale_price_usd, listing_url)
                                VALUES (?, ?, 'eBay_High_Value_Auctions', ?, ?)
                            """, (game_id, title, price_val, link_elem.get("href", "")))
                            conn.commit()
                            conn.close()
                    except ValueError:
                        continue
    except Exception:
        pass

def scrape_ebay_global_all_regions(game_title, preferred_region="US"):
    collected_prices_usd = []
    
    # Target preferred region first, then fallback to core regions to reduce request volume
    regions_to_scan = [preferred_region] + [r for r in EBAY_REGIONS if r != preferred_region]
    
    for region_code in regions_to_scan[:2]:  # Limit to 2 primary regions per run to prevent IP ban
        region_info = EBAY_REGIONS.get(region_code, EBAY_REGIONS["US"])
        domain = region_info["domain"]
        currency = region_info["currency"]
        
        search_query = f"{game_title} PS2 cib".replace(" ", "+")
        url = f"https://{domain}/sch/i.html?_nkw={search_query}&LH_BIN=1"
        
        try:
            res = session.get(url, headers=get_headers(), timeout=6)
            if res.status_code != 200:
                continue
            
            soup = BeautifulSoup(res.text, "html.parser")
            for item in soup.select(".s-item__price"):
                raw_text = item.text.split("to")[0]
                raw_text = re.sub(r"[^\d.,]", "", raw_text)
                
                if "," in raw_text and "." not in raw_text:
                    raw_text = raw_text.replace(",", ".")
                elif "," in raw_text and "." in raw_text:
                    raw_text = raw_text.replace(",", "")
                    
                try:
                    price_val = float(raw_text)
                    usd_rate = CURRENCY_RATES_TO_USD.get(currency, 1.0)
                    usd_converted = price_val * usd_rate
                    
                    if 1.0 <= usd_converted <= 10000.0:
                        collected_prices_usd.append(usd_converted)
                except ValueError:
                    continue
            
            time.sleep(1.0)
        except Exception:
            continue
            
    if collected_prices_usd:
        avg_usd = round(sum(collected_prices_usd) / len(collected_prices_usd), 2)
        return avg_usd, len(collected_prices_usd)
        
    return None, 0

def run_scraper():
    init_extended_tables()
    
    print("Scraping news feeds...")
    scrape_retro_news()
    
    conn = get_db()
    cursor = conn.cursor()
    games = cursor.execute("SELECT game_id, title, region FROM games").fetchall()
    print(f"Running Market Engine across {len(games)} titles...")
    
    for g in games:
        game_id, title, region = g["game_id"], g["title"], g["region"]
        
        # 1. Record Sale Check
        check_auction_record_sales(game_id, title)
        
        # 2. Marketplace Scan (Fixed function call)
        pref_region = "UK" if region == "PAL" else "US"
        ebay_price_usd, ebay_vol = scrape_ebay_global_all_regions(title, preferred_region=pref_region)
        
        if ebay_price_usd:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, 'eBay', 'CIB', ?, ?)
            """, (game_id, ebay_price_usd, ebay_vol))
            
            cursor.execute("""
                INSERT INTO market_index (game_id, cib_weighted_price, market_cap_contribution)
                VALUES (?, ?, ?)
            """, (game_id, ebay_price_usd, ebay_price_usd * max(ebay_vol, 1)))
            
        time.sleep(1.5)
        
    conn.commit()
    conn.close()
    print("Full scraper execution completed.")

if __name__ == "__main__":
    run_scraper()
