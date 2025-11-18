import telebot
import sqlite3
import datetime
import random
from PIL import Image, ImageDraw, ImageFont

API_KEY = os.getenv("API_KEY")  # add in Render → Environment → API_KEY=xxxx
bot = telebot.TeleBot(API_KEY)

# -------------------------
# DATABASE INIT
# -------------------------
conn = sqlite3.connect("grok.db", check_same_thread=False)
cursor = conn.cursor()

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

# -------------------------
# EVOLUTION SYSTEM
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
# USER MANAGEMENT
# -------------------------

def get_user(user_id, username=None):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()
        return get_user(user_id, username)

    return row

def add_xp(user_id, amount):
    user = get_user(user_id)
    current_xp = user[1] + amount
    new_level = get_level(current_xp)
    new_form = evolve(new_level)

    cursor.execute("""
        UPDATE users SET xp = ?, level = ?, form = ? WHERE user_id = ?
    """, (current_xp, new_level, new_form, user_id))
    conn.commit()

# -------------------------
# DAILY QUESTS
# -------------------------

def reset_daily_quests(user_id):
    today = datetime.date.today().isoformat()
    cursor.execute("""
        UPDATE daily_quests
        SET quest_hop = 0, quest_hopium = 0, quest_fight = 0, reset_date = ?
        WHERE user_id = ?
    """, (today, user_id))
    conn.commit()

def get_quests(user_id):
    today = datetime.date.today().isoformat()

    cursor.execute("SELECT * FROM daily_quests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)",
            (user_id, today)
        )
        conn.commit()
        return get_quests(user_id)

    _, hop, hopium, fight, reset_date = row

    if reset_date != today:
        reset_daily_quests(user_id)

    return {"hop": hop, "hopium": hopium, "fight": fight}

# -------------------------
# PROFILE CARD GENERATOR
# -------------------------

def generate_profile_card(username, xp, level, form):
    width, height = 600, 350
    card = Image.new("RGB", (width, height), (25, 25, 35))
    draw = ImageDraw.Draw(card)

    font_large = ImageFont.truetype("arial.ttf", 40)
    font_small = ImageFont.truetype("arial.ttf", 28)

    # Frame
    draw.rectangle([10, 10, width - 10, height - 10], outline=(80, 200, 120), width=4)

    # Text
    draw.text((30, 30), f"MegaGrok Profile", font=font_large, fill=(120, 255, 150))
    draw.text((30, 110), f"User: @{username}", font=font_small, fill=(255, 255, 255))
    draw.text((30, 160), f"Level: {level}", font=font_small, fill=(180, 255, 180))
    draw.text((30, 210), f"XP: {xp}", font=font_small, fill=(180, 220, 255))
    draw.text((30, 260), f"Form: {form}", font=font_small, fill=(255, 220, 150))

    # Save
    filename = f"profile_{username}.png"
    card.save(filename)

    return filename

# -------------------------
# BOT COMMANDS
# -------------------------

@bot.message_handler(commands=['start'])
def start(message):
    username = message.from_user.username
    user_id = message.from_user.id
    get_user(user_id, username)

    bot.reply_to(message,
        "🐸 Welcome to **MegaGrok Evolution Bot!**\n"
        "Use /growmygrok to gain XP."
    )

@bot.message_handler(commands=['growmygrok'])
def grow(message):
    user_id = message.from_user.id
    xp_gain = random.randint(10, 30)
    add_xp(user_id, xp_gain)
    bot.reply_to(message, f"✨ Your MegaGrok grows! +{xp_gain} XP")

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    username = message.from_user.username
    user = get_user(user_id, username)

    xp = user[1]
    level = user[2]
    form = user[3]

    img = generate_profile_card(username, xp, level, form)
    with open(img, "rb") as f:
        bot.send_photo(message.chat.id, f)

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    cursor.execute("SELECT username, xp FROM users ORDER BY xp DESC LIMIT 10")
    top = cursor.fetchall()

    text = "🏆 **MegaGrok Leaderboard**\n\n"
    rank = 1

    for user, xp in top:
        text += f"{rank}. @{user} — {xp} XP\n"
        rank += 1

    bot.reply_to(message, text)

# -------------------------
# START BOT
# -------------------------
bot.polling()
