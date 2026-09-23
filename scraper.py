import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re

DB_NAME = "ps2_market.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

POSITIVE_WORDS = ["pickup", "grail", "gem", "love", "worth", "collection", "found", "deal", "steal", "nostalgia", "cib"]
NEGATIVE_WORDS = ["overpriced", "expensive", "scam", "fake", "reseller", "damaged", "ruined", "skip", "worst", "loose"]

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------------------------------------------------
# 1. CIB MARKETPLACE & RETAIL SCRAPERS
# -------------------------------------------------------------------
def scrape_ebay_cib(game_title, region):
    """Scrapes active eBay listings filtered STRICTLY for Complete in Box (CIB)."""
    search_query = f"{game_title} PS2 {region} CIB Complete".replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={search_query}&_sacat=139973&LH_BIN=1"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None, 0
        
        soup = BeautifulSoup(res.text, "html.parser")
        prices = []
        
        for item in soup.select(".s-item__price"):
            text = item.text.replace("$", "").replace("£", "").replace("EUR", "").replace(",", "").strip()
            try:
                val = float(text.split(" to ")[0])
                prices.append(val)
            except ValueError:
                continue
        
        # Exclude top/bottom outliers
        valid = prices[1:8] if len(prices) > 2 else prices
        avg = round(sum(valid) / len(valid), 2) if valid else 0.0
        return avg, len(prices)
    except Exception as e:
        print(f"[eBay Error] {game_title}: {e}")
        return None, 0

def scrape_cex_uk(game_title):
    """Scrapes CeX UK for official CIB price & live stock availability."""
    url = f"https://ws-eu.cex.home.ngsl.ws/v2/boxes?q={game_title.replace(' ', '%20')}&firstRecord=1&count=5"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None, "Out of Stock"
            
        data = res.json()
        boxes = data.get("response", {}).get("data", {}).get("boxes", [])
        
        for box in boxes:
            if "PS2" in box.get("categoryName", ""):
                price = float(box.get("sellPrice", 0.0))
                out_of_stock = box.get("outOfStock", 1)
                status = "In Stock" if out_of_stock == 0 else "Out of Stock"
                return price, status
                
        return None, "Out of Stock"
    except Exception:
        return None, "Out of Stock"

# -------------------------------------------------------------------
# 2. EXPANDED REDDIT SENTIMENT & BUZZ TRACKER
# -------------------------------------------------------------------
def scrape_reddit_ecosystem(game_title):
    """Queries wide array of retro and PS2 subreddits."""
    subreddits = ["ps2", "gamecollecting", "retrogaming", "survivalsquad", "JRPG"]
    total_posts = 0
    total_upvotes = 0
    total_comments = 0
    sentiment_score = 0.0
    
    reddit_headers = {"User-Agent": "ps2-market-index-bot/2.0"}
    
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json?q={game_title.replace(' ', '+')}&restrict_sr=1&sort=new&limit=10"
        try:
            res = requests.get(url, headers=reddit_headers, timeout=10)
            if res.status_code != 200:
                continue
                
            posts = res.json().get("data", {}).get("children", [])
            for p in posts:
                data = p.get("data", {})
                title = data.get("title", "").lower()
                text = data.get("selftext", "").lower()
                full_body = f"{title} {text}"
                
                if game_title.lower() in title:
                    total_posts += 1
                    total_upvotes += data.get("score", 0)
                    total_comments += data.get("num_comments", 0)
                    
                    pos = sum(1 for w in POSITIVE_WORDS if w in full_body)
                    neg = sum(1 for w in NEGATIVE_WORDS if w in full_body)
                    if pos + neg > 0:
                        sentiment_score += (pos - neg) / (pos + neg)
                        
            time.sleep(1) # Rate limit delay
        except Exception:
            continue
            
    avg_sentiment = round(sentiment_score / total_posts, 2) if total_posts > 0 else 0.0
    return total_posts, total_upvotes, total_comments, avg_sentiment

# -------------------------------------------------------------------
# 3. MAIN INDEX SCRAPER
# -------------------------------------------------------------------
def run_scraper():
    conn = get_db()
    cursor = conn.cursor()
    
    games = cursor.execute("SELECT game_id, title, region FROM games").fetchall()
    print(f"Executing market scan for {len(games)} catalog titles...")
    
    for g in games:
        game_id, title, region = g["game_id"], g["title"], g["region"]
        
        # 1. Fetch eBay CIB Data
        ebay_cib, ebay_vol = scrape_ebay_cib(title, region)
        if ebay_cib:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, 'eBay_CIB', 'CIB', ?, ?)
            """, (game_id, ebay_cib, ebay_vol))
            
        # 2. Fetch CeX Stock & Pricing
        cex_price, cex_stock = scrape_cex_uk(title)
        if cex_price:
            cursor.execute("""
                INSERT INTO price_history (game_id, source, condition, price_amount, volume_active)
                VALUES (?, 'CeX_Retail', 'CIB', ?, ?)
            """, (game_id, cex_price, 1 if cex_stock == "In Stock" else 0))
            
        # 3. Fetch Reddit Ecosystem Sentiment
        posts, upvotes, comments, sentiment = scrape_reddit_ecosystem(title)
        cursor.execute("""
            INSERT INTO social_metrics (game_id, platform, post_count, total_upvotes, total_comments, avg_sentiment)
            VALUES (?, 'Reddit_Ecosystem', ?, ?, ?, ?)
        """, (game_id, posts, upvotes, comments, sentiment))
        
        # 4. Calculate CIB TradingView Composite Index
        sources = [p for p in [ebay_cib, cex_price] if p and p > 0]
        cib_index_price = round(sum(sources) / len(sources), 2) if sources else 0.0
        
        cursor.execute("""
            INSERT INTO market_index (game_id, cib_weighted_price, market_cap_contribution)
            VALUES (?, ?, ?)
        """, (game_id, cib_index_price, cib_index_price * max(ebay_vol, 1)))
        
        time.sleep(1.5)
        
    conn.commit()
    conn.close()
    print("Marketplace scan complete. CIB Index updated.")

if __name__ == "__main__":
    run_scraper()
