import sqlite3
from pathlib import Path

DB_PATH = Path("grok.db")

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()

def init_db():
    conn, cursor = get_db()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        form TEXT DEFAULT 'Tadpole',
        username TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_quests (
        user_id INTEGER PRIMARY KEY,
        quest_hop INTEGER DEFAULT 0,
        quest_hopium INTEGER DEFAULT 0,
        quest_fight INTEGER DEFAULT 0,
        reset_date TEXT
    )
    """)
    conn.commit()
    conn.close()
