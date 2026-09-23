-- 1. MASTER GAME CATALOG
CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    region VARCHAR(10) CHECK(region IN ('NTSC-U', 'PAL', 'NTSC-J')),
    serial_number VARCHAR(50),
    genre VARCHAR(50),
    release_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(title, region)
);

-- 2. PRICE SNAPSHOTS
CREATE TABLE IF NOT EXISTS price_history (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    source VARCHAR(50),
    condition VARCHAR(20),
    currency VARCHAR(5) DEFAULT 'USD',
    price_amount DECIMAL(10, 2),
    volume_active INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(game_id)
);

-- 3. WEIGHTED MARKET PRICE INDEX
CREATE TABLE IF NOT EXISTS market_index (
    index_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    cib_weighted_price DECIMAL(10, 2),
    loose_weighted_price DECIMAL(10, 2),
    sealed_weighted_price DECIMAL(10, 2),
    market_cap_contribution DECIMAL(12, 2),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(game_id)
);

-- 4. SOCIAL MEDIA BUZZ & SENTIMENT
CREATE TABLE IF NOT EXISTS social_metrics (
    social_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NULL,
    platform VARCHAR(30),
    subreddit VARCHAR(50),
    post_count INTEGER,
    total_upvotes INTEGER,
    total_comments INTEGER,
    avg_sentiment DECIMAL(3, 2),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(game_id)
);

-- INDEXES FOR FAST QUERYING
CREATE INDEX IF NOT EXISTS idx_price_game_time ON price_history(game_id, scraped_at);
CREATE INDEX IF NOT EXISTS idx_index_game_time ON market_index(game_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_social_time ON social_metrics(scraped_at);
