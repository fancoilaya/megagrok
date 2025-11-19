import os
import telebot
import sqlite3
import datetime
import random
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# Load API Key (set this in Render → Environment → API_KEY=XXXX)
# ============================================================

API_KEY = os.getenv("API_KEY")
bot = telebot.TeleBot(API_KEY)

# ============================================================
# Database Setup
# ============================================================

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

# ============================================================
# Evolution System
# ============================================================

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

# ============================================================
# User Management
# ============================================================

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
    current_xp = max(user[1] + amount, 0)
    new_level = max(get_level(current_xp), 1)
    new_form = evolve(new_level)

    cursor.execute("""
        UPDATE users
        SET xp = ?, level = ?, form = ?
        WHERE user_id = ?
    """, (current_xp, new_level, new_form, user_id))

    conn.commit()

# ============================================================
# Daily Quests
# ============================================================

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
        cursor.execute("""
            INSERT INTO daily_quests (user_id, reset_date)
            VALUES (?, ?)
        """, (user_id, today))
        conn.commit()
        return get_quests(user_id)

    _, hop, hopium, fight, reset_date = row

    if reset_date != today:
        reset_daily_quests(user_id)

    return {"hop": hop, "hopium": hopium, "fight": fight}

# ============================================================
# Profile Card Generator
# ============================================================

def create_profile_image(user_id, level, xp, next_level_xp, form):
    # Fix asset filenames
    asset_file = form.lower().replace(" ", "_") + ".png"
    asset_path = f"assets/{asset_file}"

    if not os.path.exists(asset_path):
        raise Exception(f"Missing asset: {asset_path}")

    grok_img = Image.open(asset_path).convert("RGBA")

    # Create base card
    card = Image.new("RGBA", (600, 800), (20, 20, 30, 255))
    draw = ImageDraw.Draw(card)

    # Resize & position character
    grok_img = grok_img.resize((400, 400))
    card.paste(grok_img, (100, 80), grok_img)

    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        small_font = ImageFont.truetype("arial.ttf", 28)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Helper function for measuring text
    def text_size(txt, fnt):
        box = draw.textbbox((0, 0), txt, font=fnt)
        width = box[2] - box[0]
        height = box[3] - box[1]
        return width, height

    # Title
    title = f"LEVEL {level} — {form.upper()}"
    tw, th = text_size(title, font)
    draw.text(((600 - tw) / 2, 20), title, fill="white", font=font)

    # XP text
    xp_text = f"XP: {xp} / {next_level_xp}"
    draw.text((50, 520), xp_text, fill="white", font=small_font)

    # XP bar bg
    draw.rectangle((50, 570, 550, 610), fill=(60, 60, 80))

    # XP bar
    progress = min(max(xp / next_level_xp, 0), 1)
    bar_width = int(500 * progress)
    draw.rectangle((50, 570, 50 + bar_width, 610), fill=(110, 200, 100))

    # Footer
    footer = "MegaGrok Evolution Bot"
    fw, fh = text_size(footer, small_font)
    draw.text(((600 - fw) / 2, 750), footer, fill="#8bf", font=small_font)

    # Save
    os.makedirs("profiles", exist_ok=True)
    output_path = f"profiles/{user_id}.png"
    card.save(output_path)

    return output_path

# ============================================================
# Bot Commands
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "🐸 Welcome to **MegaGrok Evolution Bot!**\n"
        "Use /growmygrok to gain XP and evolve your Grok!\n"
        "Use /profile to view your Grok card.\n"
        "/help — List all commands.\n"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message,
        "🐸 **MegaGrok Commands**\n\n"
        "/start — Begin your journey\n"
        "/growmygrok — Gain XP\n"
        "/hop — Daily hop ritual\n"
        "/fight — Fight a FUDling\n"
        "/profile — View your Grok card\n"
        "Level up and evolve your MegaGrok!"
    )

@bot.message_handler(commands=['growmygrok'])
def grow(message):
    user_id = message.from_user.id
    xp_gain = random.randint(5, 35)

    add_xp(user_id, xp_gain)
    bot.reply_to(message, f"✨ Your MegaGrok grows! +{xp_gain} XP")

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
        bot.reply_to(message, "⚔️ You've already fought a FUDling today!")
        return

    win = random.choice([True, False])

    if win:
        xp_gain = random.randint(50, 150)
        bot.reply_to(message, f"⚡🐸 You crushed a FUDling! +{xp_gain} XP")
    else:
        xp_gain = random.randint(10, 20)
        bot.reply_to(message, f"😵 You slipped! But gained wisdom +{xp_gain} XP")

    add_xp(user_id, xp_gain)

    cursor.execute("UPDATE daily_quests SET quest_fight = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

@bot.message_handler(commands=['profile'])
def profile(message):
    try:
        user_id = message.from_user.id
        user = get_user(user_id)

        xp = user[1]
        level = user[2]
        form = user[3]
        next_level_xp = level * 200

        path = create_profile_image(user_id, level, xp, next_level_xp, form)
        with open(path, "rb") as img:
            bot.send_photo(message.chat.id, img)

    except Exception as e:
        bot.reply_to(message, f"❌ Could not generate profile image: {str(e)}")

# ============================================================
# Start Bot
# ============================================================

bot.polling(none_stop=True)
