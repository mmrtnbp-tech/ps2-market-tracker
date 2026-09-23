import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

DB_NAME = "ps2_market.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

st.set_page_config(page_title="PS2 Market Index Terminal", layout="wide")

st.title("🎮 PS2 Global Market Terminal")
st.caption("Live CIB Pricing (eBay + CeX UK) & Social Sentiment Tracking")

conn = get_connection()

# -------------------------------------------------------------------
# 1. TOP LEVEL METRICS & MARKET CAP
# -------------------------------------------------------------------
try:
    total_games = pd.read_sql("SELECT COUNT(*) as count FROM games", conn)["count"][0]
    total_market_cap = pd.read_sql("SELECT SUM(market_cap_contribution) as cap FROM market_index", conn)["cap"][0] or 0.0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Catalog Games Tracked", f"{total_games}")
    col2.metric("Total PS2 Index Market Cap", f"${total_market_cap:,.2f}")
    col3.metric("Data Engine Status", "Active (6h Schedule)")
except Exception:
    st.info("Database initializing... Run your workflow to populate live market statistics.")

st.divider()

# -------------------------------------------------------------------
# 2. SEARCH & INDIVIDUAL GAME TERMINAL
# -------------------------------------------------------------------
games_df = pd.read_sql("SELECT game_id, title, region FROM games", conn)

if not games_df.empty:
    search_query = st.text_input("🔍 Search PS2 Game Title (e.g. Silent Hill, Rule of Rose):", "")
    
    filtered_games = games_df[games_df["title"].str.contains(search_query, case=False, na=False)]
    
    if not filtered_games.empty:
        selected_game_str = st.selectbox(
            "Select Game Title Variant:", 
            filtered_games.apply(lambda row: f"[{row['region']}] {row['title']} (ID: {row['game_id']})", axis=1)
        )
        
        # Extract selected game ID
        selected_id = int(selected_game_str.split("ID: ")[1].replace(")", ""))
        
        st.subheader(f"Market Analytics: {selected_game_str}")
        
        # Load Price History for Charting
        price_df = pd.read_sql("""
            SELECT source, condition, price_amount, scraped_at 
            FROM price_history 
            WHERE game_id = ? 
            ORDER BY scraped_at ASC
        """, conn, params=(selected_id,))
        
        # Load Social Metrics
        social_df = pd.read_sql("""
            SELECT platform, post_count, total_upvotes, total_comments, avg_sentiment, scraped_at 
            FROM social_metrics 
            WHERE game_id = ? 
            ORDER BY scraped_at DESC
        """, conn, params=(selected_id,))
        
        tab1, tab2 = st.tabs(["📈 CIB Price History Chart", "💬 Reddit Sentiment & Hype"])
        
        with tab1:
            if not price_df.empty:
                fig = px.line(
                    price_df, 
                    x="scraped_at", 
                    y="price_amount", 
                    color="source",
                    title="Complete-In-Box (CIB) Valuation Trend",
                    labels={"scraped_at": "Date", "price_amount": "Price ($)"}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No price data points recorded yet for this title.")
                
        with tab2:
            if not social_df.empty:
                s_col1, s_col2, s_col3 = st.columns(3)
                latest_social = social_df.iloc[0]
                
                s_col1.metric("Recent Reddit Posts", f"{latest_social['post_count']}")
                s_col2.metric("Total Community Upvotes", f"{latest_social['total_upvotes']}")
                s_col3.metric("Avg Sentiment Score (-1 to +1)", f"{latest_social['avg_sentiment']}")
                
                st.dataframe(social_df, use_container_width=True)
            else:
                st.write("No Reddit mentions recorded in the latest scan batch.")
else:
    st.warning("Catalog empty. Ensure seed_database.py has executed.")

conn.close()
