import telebot
import sqlite3
import datetime
import random

API_KEY = "8531050065:AAGdzxcixGfmlBSKWMQARxA7MDRHWlyKJFA"
bot = telebot.TeleBot(API_KEY)

# -------------------------
# Database Initialization
# -------------------------

conn = sqlite3.connect("grok.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    form TEXT DEFAULT 'Tadpole'
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

# -------------------------
# Evolution System
# -------------------------

EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended Hopper")
]

def get_level(xp):
    return xp // 200 + 1

def evolve(level):
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"

# -------------------------
# User Management
# -------------------------

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return get_user(user_id)

    return row

def add_xp(user_id, amount):
    user = get_user(user_id)
    current_xp = user[1] + amount
    new_level = get_level(current_xp)
    new_form = evolve(new_level)

    cursor.execute(
        "UPDATE users SET xp = ?, level = ?, form = ? WHERE user_id = ?",
        (current_xp, new_level, new_form, user_id)
    )
    conn.commit()

# -------------------------
# Daily Quests
# -------------------------

def reset_daily_quests(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute("""
        UPD
