import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import random
import re

DB_NAME = "ps2_market.db"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

POSITIVE_WORDS = ["pickup", "grail", "gem", "love", "worth", "collection", "found", "deal", "steal", "nostalgia", "cib"]
NEGATIVE_WORDS = ["overpriced", "expensive", "scam", "fake", "reseller", "damaged", "ruined", "skip", "worst", "loose"]

# Currency Conversion Rates to USD Standard
CURRENCY_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.09,
    "GBP": 1.28,
    "JPY": 0.0067  # JPY conversion (e.g. 1000 JPY = ~$6.70 USD)
}

EBAY_REGIONS = {
    "US": {"domain": "www.ebay.com", "currency": "USD", "terms": ["CIB Complete", "Mint Condition", "Brand New"]},
    "UK": {"domain": "www.ebay.co.uk", "currency": "GBP", "terms": ["Complete CIB", "Mint Condition", "New"]},
    "DE": {"domain": "www.ebay.de", "currency": "EUR", "terms": ["Vollständig CIB", "Sehr gut", "Neu OVP"]},
    "FR": {"domain": "www.ebay.fr", "currency": "EUR", "terms": ["Complet CIB", "Très bon état", "Neuf"]},
    "ES": {"domain": "www.ebay.es", "currency": "EUR", "terms": ["Completo CIB", "Como nuevo", "Nuevo"]},
    "IT": {"domain": "www.ebay.it", "currency": "EUR", "terms": ["Completo CIB", "Come nuovo", "Nuovo"]}
}

CEX_REGIONS = {
    "CeX_UK": {"url": "https://ws-eu.cex.home.ngsl.ws/v2/boxes?q=", "currency": "GBP"},
    "CeX_ES": {"url": "https://ws-es.cex.home.ngsl.ws/v2/boxes?q=", "currency": "EUR"},
    "CeX_IT": {"url": "https://ws-it.cex.home.ngsl.ws/v2/boxes?q=", "currency": "EUR"},
    "CeX_PT": {"url": "https://ws-pt.cex.home.ngsl.ws/v2/boxes?q=", "currency": "EUR"}
}

SUBREDDITS = [
    "ps2", "gamecollecting", "retrogaming", "survivalsquad", 
    "JRPG", "ps2viva", "gaming", "gamehunting", "thriftstorehauls"
]

session = requests.Session()

def get_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------------------------------------------------
# 1. INTERNATIONAL EBAY SCRAPER
# -------------------------------------------------------------------
def scrape_ebay_global(game_title, region_code):
    region_info = EBAY_REGIONS.get(region_code, EBAY_REGIONS["US"])
    domain = region_info["domain"]
    currency = region_info["currency"]
    terms = region_info["terms"]
    
    collected_prices_usd = []
    
    for keyword in terms[:2]:
        search_query = f"{game_title} PS2 {keyword}".replace(" ", "+")
        url = f"https://{domain}/sch/i.html?_nkw={search_query}&_sacat=139973&LH_BIN=1"
        
        try:
            res = session.get(url, headers=get_headers(), timeout=6)
            if res.status_code != 200:
                continue
            
            soup = BeautifulSoup(res.text, "html.parser")
            for item in soup.select(".s-item__price"):
                raw_text = item.text.replace("$", "").replace("£", "").replace("EUR", "").replace("€", "").strip()
                raw_text = raw_text.split(" to ")[0].split(" bis ")[0]
                
                if "," in raw_text and "." not in raw_text:
                    raw_text = raw_text.replace(",", ".")
                elif "," in raw_text and "." in raw_text:
                    raw_text = raw_text.replace(",", "")
                    
                try:
                    price_val = float(re.sub(r"[^\d.]", "", raw_text))
                    usd_converted = price_val * CURRENCY_RATES_TO_USD.get(currency, 1.0)
                    if 1.0 <= usd_converted <= 2000.0:
                        collected_prices_usd.append(usd_converted)
                except ValueError:
                    continue
            
            time.sleep(random.uniform(0.3, 0.5))
        except Exception:
            continue
            
    if collected_prices_usd:
        valid = collected_prices_usd[1:-1] if len(collected_prices_usd) > 3 else collected_prices_usd
        avg_usd = round(sum(valid) / len(valid), 2)
        return avg_usd, len(collected_prices_usd)
        
    return None, 0

# -------------------------------------------------------------------
# 2. EUROPEAN RETAIL SCRAPER (CeX UK, ES, IT, PT)
# -------------------------------------------------------------------
def scrape_cex_all_regions(game_title):
    results = []
    for region_name, config in CEX_REGIONS.items():
        endpoint = f"{config['url']}{game_title.replace(' ', '%20')}&firstRecord=1&count=3"
        try:
            res = session.get(endpoint, headers=get_headers(), timeout=6)
            if res.status_code != 200:
                continue
                
            boxes = res.json().get("response", {}).get("data", {}).get("boxes", [])
            for box in boxes:
                if "PS2" in box.get("categoryName", ""):
                    local_price = float(box.get("sellPrice", 0.0))
                    usd_price = round(local_price * CURRENCY_RATES_TO_USD[config["currency"]], 2)
                    status = "In Stock" if box.get("outOfStock", 1) == 0 else "Out of Stock"
                    results.append((region_name, usd_price, status))
                    break
        except Exception:
            continue
        time.sleep(0.3)
    return results

# -------------------------------------------------------------------
# 3. NORTH AMERICAN SPECIALIST RETAIL SCRAPER (eStarland US)
# -------------------------------------------------------------------
def scrape_estarland_us(game_title):
    """Scrapes eStarland US for retail CIB PS2 prices."""
    url = f"https://www.estarland.com/api/v1/search?q={game_title.replace(' ', '%20')}&category=PS2"
    try:
        res = session.get(url, headers=get_headers(), timeout=6)
        if res.status_code == 200:
            data = res.json()
            products = data.get("products", [])
            for prod in products:
                if "PlayStation 2" in prod.get("category_name", ""):
                    price = float(prod.get("price", 0.0))
                    if price > 0:
                        return price, "In Stock" if prod.get("in_stock", False) else "Out of Stock"
    except Exception:
        pass
    return None, "Out of Stock"

# -------------------------------------------------------------------
# 4. ASIAN / JAPANESE IMPORT MARKET SCRAPER (Surugaya & Buyee JP)
# -------------------------------------------------------------------
def scrape_japan_import_market(game_title):
    """Scrapes Japanese proxy feeds (Buyee/Surugaya) for NTSC-J PS2 title prices in JPY -> USD."""
    search_query = f"{game_title} PS2".replace(" ", "+")
    url = f"https://buyee.jp/item/search/query/{search_query}/category/2084062822" # PS2 category
    
    try:
        res = session.get(url, headers=get_headers(), timeout=6)
        if res.status_code != 200:
            return None
            
        soup = BeautifulSoup(res.text, "html.parser")
        jpy_prices = []
        
        for item in soup.select(".g-price"):
            text = item.text.replace("yen", "").replace("円", "").replace(",", "").strip()
            try:
                jpy_val = float(re.sub(r"[^\d.]", "", text))
                if jpy_val > 100:
                    jpy_prices.append(jpy_val)
            except ValueError:
                continue
                
        if jpy_prices:
            avg_jpy = sum(jpy_prices[:5]) / len(jpy_prices[:5])
            usd_price = round(avg_jpy * CURRENCY_RATES_TO_USD["JPY"], 2)
            return usd_price
    except Exception:
        pass
    return None

# -------------------------------------------------------------------
# 5. DYNAMIC REDDIT TRAFFIC TRACKER
# -------------------------------------------------------------------
def scrape_reddit_dynamic_keywords(game_title):
    keyword_variations = [game_title, f"{game_title} PS2", f"{game_title} CIB"]
    total_posts = 0
    total_upvotes = 0
    total_comments = 0
    sentiment_score = 0.0
    
    for kw in keyword_variations:
        for sub in SUBREDDITS[:4]:
            url = f"https://www.reddit.com/r/{sub}/search.json?q={kw.replace(' ', '+')}&restrict_sr=1&sort=new&limit=5"
            try:
                res = session.get(url, headers=get_headers(), timeout=6)
                if res.status_code == 429:
                    time.sleep(8.0)
                    continue
                elif res.status_code != 200:
                    continue
                    
                posts = res.json().get("data", {}).get("children", [])
                for p in posts:
                    data = p.get("data", {})
                    title = data.get("title", "").lower()
                    text = data.get("selftext", "").lower()
                    full_body = f"{title} {text}"
                    
                    total_posts += 1
                    total_upvotes += data.get("score", 0)
                    total_comments += data.get("num_comments", 0)
                    
                    pos = sum(1 for w in POSITIVE_WORDS if w in full_body)
                    neg = sum(1 for w in NEGATIVE_WORDS if w in full_body)
                    if pos + neg > 0:
                        sentiment_score += (pos - neg) / (pos + neg)
                        
                time.sleep(0.8)
            except Exception:
                continue
                
    avg_sentiment = round(sentiment_score / total_posts, 2) if total_posts > 0 else 0.0
    return total_posts, total_upvotes, total_comments, avg_sentiment

# -------------------------------------------------------------------
# 6. MASTER EXECUTION ENGINE
# -------------------------------------------------------------------
def run_scraper():
    conn = get_db()
    cursor = conn.cursor()
    
    games = cursor.execute("SELECT game_id, title, region FROM games").fetchall()
    print(f"Executing Global (US, Europe, Asia) Scan for {len(games)} catalog titles...")
    
    for g in games:
        game_id, title, region = g["game_id"], g["title"], g["region"]
        ebay_region_target = "UK" if region == "PAL" else ("US" if region == "NTSC-U" else "DE")
        
        # 1. Global eBay
        ebay_price_usd, ebay_vol = scrape_ebay_global(title, ebay_region_target)
        if ebay_price_usd:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, ?, 'CIB', ?, ?)
            """, (game_id, f"eBay_{ebay_region_target}", ebay_price_usd, ebay_vol))
            
        # 2. European CeX Network (UK, ES, IT, PT)
        cex_data = scrape_cex_all_regions(title)
        cex_prices_found = []
        for cex_source, cex_usd_price, cex_stock in cex_data:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, ?, 'CIB', ?, ?)
            """, (game_id, cex_source, cex_usd_price, 1 if cex_stock == "In Stock" else 0))
            cex_prices_found.append(cex_usd_price)
            
        # 3. US Retail Specialist (eStarland)
        us_retail_price, us_stock = scrape_estarland_us(title)
        if us_retail_price:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, 'eStarland_US', 'CIB', ?, ?)
            """, (game_id, us_retail_price, 1 if us_stock == "In Stock" else 0))
            
        # 4. Asian / NTSC-J Import Market (Buyee / Surugaya JP)
        if region == "NTSC-J":
            jp_price_usd = scrape_japan_import_market(title)
            if jp_price_usd:
                cursor.execute("""
                    INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                    VALUES (?, 'Buyee_Surugaya_JP', 'CIB', ?, 1)
                """, (game_id, jp_price_usd))
                
        # 5. Dynamic Reddit Traffic Scan
        posts, upvotes, comments, sentiment = scrape_reddit_dynamic_keywords(title)
        cursor.execute("""
            INSERT INTO social_metrics (game_id, platform, post_count, total_upvotes, total_comments, avg_sentiment)
            VALUES (?, 'Reddit_Dynamic_Keywords', ?, ?, ?, ?)
        """, (game_id, posts, upvotes, comments, sentiment))
        
        # 6. Master Index Weight Calculation
        all_prices = [p for p in ([ebay_price_usd, us_retail_price] + cex_prices_found) if p and p > 0]
        cib_index_price = round(sum(all_prices) / len(all_prices), 2) if all_prices else 0.0
        
        cursor.execute("""
            INSERT INTO market_index (game_id, cib_weighted_price, market_cap_contribution)
            VALUES (?, ?, ?)
        """, (game_id, cib_index_price, cib_index_price * max(ebay_vol, 1)))
        
        time.sleep(random.uniform(0.5, 1.0))
        
    conn.commit()
    conn.close()
    print("Global multi-region market scan complete.")

if __name__ == "__main__":
    run_scraper()
