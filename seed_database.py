import sqlite3
import requests
import json
import time

DB_NAME = "ps2_market.db"

STARTER_CATALOG = [
    # NTSC-U (North America)
    {"title": "Silent Hill 2", "region": "NTSC-U", "serial": "SLUS-20228", "genre": "Horror", "year": 2001},
    {"title": "Rule of Rose", "region": "NTSC-U", "serial": "SLUS-21448", "genre": "Horror", "year": 2006},
    {"title": "Def Jam: Fight for NY", "region": "NTSC-U", "serial": "SLUS-21004", "genre": "Fighting", "year": 2004},
    {"title": "Kuon", "region": "NTSC-U", "serial": "SLUS-21008", "genre": "Horror", "year": 2004},
    {"title": "Dragon Ball Z: Budokai Tenkaichi 3", "region": "NTSC-U", "serial": "SLUS-21678", "genre": "Fighting", "year": 2007},
    
    # PAL (Europe)
    {"title": "Silent Hill 2", "region": "PAL", "serial": "SLES-50382", "genre": "Horror", "year": 2001},
    {"title": "Rule of Rose", "region": "PAL", "serial": "SLES-54331", "genre": "Horror", "year": 2006},
    {"title": "Def Jam: Fight for NY", "region": "PAL", "serial": "SLES-52591", "genre": "Fighting", "year": 2004},
    {"title": "Gregory Horror Show", "region": "PAL", "serial": "SLES-51881", "genre": "Adventure", "year": 2003},
    {"title": "Michigan: Report from Hell", "region": "PAL", "serial": "SLES-53093", "genre": "Horror", "year": 2005},
    
    # NTSC-J (Japan)
    {"title": "Silent Hill 2", "region": "NTSC-J", "serial": "SLPM-65014", "genre": "Horror", "year": 2001},
    {"title": "Rule of Rose", "region": "NTSC-J", "serial": "SLPM-66192", "genre": "Horror", "year": 2006},
    {"title": "Berserk: Millennium Falcon Hen Seima Senki no Sho", "region": "NTSC-J", "serial": "SLPM-65688", "genre": "Action", "year": 2004},
    {"title": "Siren 2", "region": "NTSC-J", "serial": "SCPS-15103", "genre": "Horror", "year": 2006},
    {"title": "Initial D Special Stage", "region": "NTSC-J", "serial": "SLPM-65293", "genre": "Racing", "year": 2003}
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    with open("schema.sql", "r") as f:
        schema_script = f.read()
    cursor.executescript(schema_script)
    conn.commit()
    conn.close()
    print("Database schema initialized.")

def seed_starter_catalog():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    inserted_count = 0
    for game in STARTER_CATALOG:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO games (title, region, serial_number, genre, release_year)
                VALUES (?, ?, ?, ?, ?)
            """, (game["title"], game["region"], game["serial"], game["genre"], game["year"]))
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception as e:
            print(f"Error: {e}")
    conn.commit()
    conn.close()
    print(f"Seeded {inserted_count} initial games.")

if __name__ == "__main__":
    init_db()
    seed_starter_catalog()
