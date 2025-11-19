import os
import telebot
import sqlite3
import datetime
import random
from PIL import Image, ImageDraw, ImageFont

# =============================
# Load API Key
# =============================
API_KEY = os.getenv("API_KEY")
bot = telebot.TeleBot(API_KEY)

# =============================
# Database Setup
# =============================
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

# =============================
# Evolution
# =============================
EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended Hopper")
]

def evolve(level):
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"

# =============================
# XP + Level Logic
# =============================
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
    level = user[2]

    # Keep leveling while XP >= 200
    while xp >= 200:
        xp -= 200
        level += 1

    new_form = evolve(level)

    cursor.execute("""
        UPDATE users
        SET xp = ?, level = ?, form = ?
        WHERE user_id = ?
    """, (xp, level, new_form, user_id))
    conn.commit()

# =============================
# Daily Quests
# =============================
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
        cursor.execute("INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        conn.commit()
        return get_quests(user_id)

    _, hop, hopium, fight, reset_date = row

    if reset_date != today:
        reset_daily_quests(user_id)

    return {"hop": hop, "hopium": hopium, "fight": fight}

# =============================
# Profile Card Generator
# =============================
def generate_profile_card(username, level, xp, form):
    card = Image.new("RGBA", (600, 300), (20, 20, 20, 255))
    draw = ImageDraw.Draw(card)

    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # Select sprite
    sprite_path = f"assets/{form.lower()}.png"
    if not os.path.exists(sprite_path):
        sprite_path = "assets/tadpole.png"

    sprite = Image.open(sprite_path).convert("RGBA")
    sprite = sprite.resize((200, 200))

    card.paste(sprite, (20, 50), sprite)

    draw.text((250, 40), f"{username}", fill="white", font=font_large)
    draw.text((250, 80), f"Form: {form}", fill="white", font=font_small)
    draw.text((250, 110), f"Level: {level}", fill="white", font=font_small)
    draw.text((250, 140), f"XP: {xp}/200", fill="white", font=font_small)

    bar_x = 250
    bar_y = 180
    bar_width = 300
    filled = int((xp / 200) * bar_width)

    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + 25], fill=(60, 60, 60))
    draw.rectangle([bar_x, bar_y, bar_x + filled, bar_y + 25], fill=(0, 200, 0))

    output = "/tmp/profile.png"
    card.save(output)

    return output

# =============================
# Commands
# =============================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "🐸 Welcome to MegaGrok Evolution Bot!\n"
        "Use /growmygrok to gain XP.\n"
        "Use /profile to see your Grok.\n"
        "Use /leaderboard to see the top players.\n"
        "Use /help to see commands.\n"                 
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🐸 *MegaGrok Bot Commands*\n\n"
        "/start – Begin your MegaGrok journey\n"
        "/help – Show this help menu\n"
        "/profile – View your Grok’s profile card\n"
        "/growmygrok – Gain XP (Randomized)\n"
        "/hop – Daily Hop Ritual (1/day)\n"
        "/fight – Fight a FUDling for XP (1/day)\n"
        "/leaderboard – View the top MegaGrok players\n\n"
        "✨ Level up your Grok, complete quests, and evolve into legendary forms!"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")


@bot.message_handler(commands=['growmygrok'])
def grow(message):
    user_id = message.from_user.id
    xp_gain = random.randint(-10, 30)

    add_xp(user_id, xp_gain)
    user = get_user(user_id)
    level = user[2]
    xp = user[1]

    progress_blocks = int((xp / 200) * 10)
    bar = "[" + "█" * progress_blocks + "-" * (10 - progress_blocks) + "]"

    bot.reply_to(message,
        f"✨ Your MegaGrok grows! {xp_gain:+} XP\n"
        f"Level: {level}\n"
        f"XP: {xp}/200\n"
        f"{bar}"
    )

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    xp = user[1]
    level = user[2]
    form = user[3]

    username = message.from_user.first_name

    try:
        img_path = generate_profile_card(username, level, xp, form)
        with open(img_path, "rb") as photo:
            bot.send_photo(message.chat.id, photo)
    except Exception as e:
        bot.reply_to(message, f"Error generating profile: {e}")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    cursor.execute("""
        SELECT user_id, xp, level, form
        FROM users
        ORDER BY level DESC, xp DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()

    if not rows:
        bot.reply_to(message, "No players yet.")
        return

    text = "🏆 *MegaGrok Leaderboard* 🏆\n\n"
    rank = 1

    for user_id, xp, level, form in rows:
        try:
            user_info = bot.get_chat(user_id)
            username = user_info.first_name
        except:
            username = f"User {user_id}"

        text += (
            f"{rank}. 🐸 *{username}*\n"
            f"   Level {level} — {form}\n"
            f"   {xp}/200 XP\n\n"
        )
        rank += 1

    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['hop'])
def hop(message):
    user_id = message.from_user.id
    quests = get_quests(user_id)

    if quests["hop"] == 1:
        bot.reply_to(message, "🐸 You've already done your Hop Ritual today!")
        return

    xp_gain = random.randint(20, 50)
    add_xp(user_id, xp_gain)

    cursor.execute("UPDATE daily_quests SET quest_hop = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    bot.reply_to(message, f"🐸✨ Hop Ritual complete! +{xp_gain} XP")

@bot.message_handler(commands=['fight'])
def fight(message):
    user_id = message.from_user.id
    quests = get_quests(user_id)

    if quests["fight"] == 1:
        bot.reply_to(message, "⚔️ Already fought today!")
        return

    win = random.choice([True, False])

    if win:
        xp = random.randint(50, 150)
        bot.reply_to(message, f"⚡🐸 Victory! +{xp} XP")
    else:
        xp = random.randint(10, 20)
        bot.reply_to(message, f"😵 You slipped... +{xp} XP")

    add_xp(user_id, xp)

    cursor.execute("UPDATE daily_quests SET quest_fight = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# =============================
# Start
# =============================
bot.polling(none_stop=True)
