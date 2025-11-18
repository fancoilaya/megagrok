import telebot
import sqlite3
import datetime
import random

API_KEY = "YOUR_API_KEY_HERE"
bot = telebot.TeleBot(API_KEY)

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

# Evolution tiers
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
    xp = user[1] + amount
    level = get_level(xp)
    form = evolve(level)

    cursor.execute(
        "UPDATE users SET xp = ?, level = ?, form = ? WHERE user_id = ?",
        (xp, level, form, user_id)
    )
    conn.commit()

def reset_daily_quests(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute("""
        UPDATE daily_quests SET quest_hop = 0, quest_hopium = 0, quest_fight = 0, reset_date = ?
        WHERE user_id = ?
    """, (today, user_id))
    conn.commit()

def get_quests(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute("SELECT * FROM daily_quests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        conn.commit()
        return get_quests(user_id)

    _, hop, hopium, fight, reset_date = row

    if reset_date != today:
        reset_daily_quests(user_id)

    return {"hop": hop, "hopium": hopium, "fight": fight}

# ------------------------------------------------------
# Commands
# ------------------------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🐸 Welcome to MegaGrok! Use /growmygrok to gain XP.")

@bot.message_handler(commands=['growmygrok'])
def grow(message):
    user_id = message.from_user.id
    xp_gain = random.randint(10, 30)
    add_xp(user_id, xp_gain)
    bot.reply_to(message, f"✨ MegaGrok grows stronger! +{xp_gain} XP")

@bot.message_handler(commands=['hop'])
def hop(message):
    user_id = message.from_user.id
    quests = get_quests(user_id)

    if quests["hop"]:
        return bot.reply_to(message, "You've already performed the Hop Ritual today!")

    xp_gain = random.randint(20, 50)
    add_xp(user_id, xp_gain)

    cursor.execute("UPDATE daily_quests SET quest_hop = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    bot.reply_to(message, f"🐸✨ Hop Ritual complete! +{xp_gain} XP")

@bot.message_handler(commands=['fight'])
def fight(message):
    user_id = message.from_user.id
    quests = get_quests(user_id)

    if quests["fight"]:
        return bot.reply_to(message, "You've already battled today!")

    win = random.choice([True, False])

    if win:
        xp = random.randint(50, 150)
        bot.reply_to(message, f"⚡🐸 You defeated a FUDling! +{xp} XP")
    else:
        xp = random.randint(10, 20)
        bot.reply_to(message, f"😵 You slipped but still learned. +{xp} XP")

    add_xp(user_id, xp)

    cursor.execute("UPDATE daily_quests SET quest_fight = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

bot.polling()
