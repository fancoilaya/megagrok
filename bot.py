#!/usr/bin/env python3
import os
import io
import random
import sqlite3
import datetime
from pathlib import Path

import telebot
from PIL import Image, ImageDraw, ImageFont, ImageOps

# -------------------------
# Configuration
# -------------------------

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable not set")

bot = telebot.TeleBot(API_KEY, parse_mode=None)

ASSETS_DIR = Path("assets")
FROG_ASSETS = {
    "Tadpole": ASSETS_DIR / "tadpole.png",
    "Hopper": ASSETS_DIR / "hopper.png",
    "Ascended Hopper": ASSETS_DIR / "ascended.png",
}
FALLBACK_ASSET = FROG_ASSETS["Tadpole"]

DB_PATH = "grok.db"

# -------------------------
# Database Initialization
# -------------------------

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
# Evolution System
# -------------------------

EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopper"),
    (10, "Ascended Hopper")
]


def get_level(xp: int) -> int:
    return xp // 200 + 1


def evolve(level: int) -> str:
    for lvl, form in reversed(EVOLUTIONS):
        if level >= lvl:
            return form
    return "Tadpole"


# -------------------------
# User / XP management
# -------------------------


def get_user(user_id: int, username: str | None = None):
    cursor.execute("SELECT user_id, xp, level, form, username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        # insert new row
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        return get_user(user_id, username)
    return {
        "user_id": row[0],
        "xp": row[1],
        "level": row[2],
        "form": row[3],
        "username": row[4] or username
    }


def add_xp(user_id: int, amount: int):
    user = get_user(user_id)
    new_xp = max(0, user["xp"] + amount)
    new_level = get_level(new_xp)
    new_form = evolve(new_level)
    cursor.execute(
        "UPDATE users SET xp = ?, level = ?, form = ? WHERE user_id = ?",
        (new_xp, new_level, new_form, user_id)
    )
    conn.commit()
    return new_xp, new_level, new_form


# -------------------------
# Daily Quests
# -------------------------


def reset_daily_quests(user_id: int):
    today = datetime.date.today().isoformat()
    cursor.execute("""
        UPDATE daily_quests
        SET quest_hop = 0, quest_hopium = 0, quest_fight = 0, reset_date = ?
        WHERE user_id = ?
    """, (today, user_id))
    conn.commit()


def get_quests(user_id: int):
    today = datetime.date.today().isoformat()
    cursor.execute("SELECT user_id, quest_hop, quest_hopium, quest_fight, reset_date FROM daily_quests WHERE user_id = ?",
                   (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO daily_quests (user_id, reset_date) VALUES (?, ?)", (user_id, today))
        conn.commit()
        return get_quests(user_id)
    _, hop, hopium, fight, reset_date = row
    if reset_date != today:
        reset_daily_quests(user_id)
    return {"hop": hop, "hopium": hopium, "fight": fight}


# -------------------------
# Helpers: fetch Telegram avatar
# -------------------------


def fetch_telegram_profile_photo(user_id: int) -> Image.Image | None:
    """
    Returns a PIL.Image (RGBA) of the largest available profile photo, or None on failure.
    """
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.total_count > 0:
            sizes = photos.photos[0]  # list of PhotoSize objects
            file_info = sizes[-1]  # largest
            file_id = file_info.file_id
            file = bot.get_file(file_id)
            raw = bot.download_file(file.file_path)
            img = Image.open(io.BytesIO(raw)).convert("RGBA")
            return img
    except Exception:
        return None
    return None


# -------------------------
# Profile card generation
# -------------------------


def generate_profile_card(user_id: int, username: str, xp: int, level: int, form: str) -> str:
    """
    Creates an image file (PNG) and returns the path.
    """
    width, height = 900, 420
    bg_color = (18, 18, 26, 255)
    card = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(card)

    # frog art (left)
    frog_path = FROG_ASSETS.get(form, FALLBACK_ASSET)
    if not Path(frog_path).exists():
        frog_img = Image.new("RGBA", (320, 320), (90, 110, 90, 255))
    else:
        frog_img = Image.open(frog_path).convert("RGBA")
    frog_img = frog_img.resize((320, 320))

    frog_x = 30
    frog_y = (height - frog_img.height) // 2
    card.paste(frog_img, (frog_x, frog_y), frog_img)

    # user avatar
    avatar = fetch_telegram_profile_photo(user_id)
    avatar_size = 140
    if avatar:
        avatar = avatar.resize((avatar_size, avatar_size))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    else:
        avatar = Image.new("RGBA", (avatar_size, avatar_size), (70, 80, 100, 255))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)

    avatar_x = 380
    avatar_y = 40
    card.paste(avatar, (avatar_x, avatar_y), mask)

    # fonts (common path on Linux)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception:
        font_big = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # username
    display_name = username or f"user_{user_id}"
    draw.text((avatar_x + avatar_size + 16, 44), f"@{display_name}", font=font_big, fill=(255, 255, 255, 255))

    # Level + form text under avatar
    draw.text((avatar_x, avatar_y + avatar_size + 12), f"Level: {level}", font=font_med, fill=(220, 220, 220, 255))
    draw.text((avatar_x + 170, avatar_y + avatar_size + 12), f"Form: {form}", font=font_med, fill=(200, 240, 200, 255))

    # XP progress
    current_level_xp = (level - 1) * 200
    next_level_xp = level * 200
    xp_into_level = xp - current_level_xp
    xp_needed = max(next_level_xp - current_level_xp, 1)
    progress = max(0.0, min(1.0, xp_into_level / xp_needed))

    draw.text((avatar_x, avatar_y + avatar_size + 56), f"XP: {xp_into_level} / {xp_needed}", font=font_small, fill=(200, 200, 200, 255))

    # progress bar
    bar_x = avatar_x
    bar_y = avatar_y + avatar_size + 90
    bar_w = 420
    bar_h = 28
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=12, fill=(60, 60, 70, 255))
    fill_w = int(bar_w * progress)
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=12, fill=(80, 220, 140, 255))

    percent_text = f"{int(progress * 100)}%"
    w_percent, _ = draw.textsize(percent_text, font=font_small)
    draw.text((bar_x + bar_w - w_percent, bar_y - 26), percent_text, font=font_small, fill=(200, 200, 200, 255))

    # stats
    power = level * 5
    defense = level * 3
    luck = level * 2
    stat_x = avatar_x
    stat_y = bar_y + bar_h + 24
    draw.text((stat_x, stat_y), f"⚔️ Power: {power}", font=font_small, fill=(220, 220, 220, 255))
    draw.text((stat_x + 220, stat_y), f"🛡 Defense: {defense}", font=font_small, fill=(220, 220, 220, 255))
    draw.text((stat_x + 440, stat_y), f"🍀 Luck: {luck}", font=font_small, fill=(220, 220, 220, 255))

    # footer
    draw.text((30, height - 28), "MegaGrok — The Cosmic Amphibian", font=font_small, fill=(120, 120, 140, 200))

    # save
    out_path = f"profile_{user_id}.png"
    card.convert("RGB").save(out_path, format="PNG")
    return out_path


# -------------------------
# Commands
# -------------------------


@bot.message_handler(commands=['start'])
def start_command(message):
    username = message.from_user.username or message.from_user.first_name or str(message.from_user.id)
    # ensure user row exists
    get_user(message.from_user.id, username)
    bot.reply_to(message,
                 "🐸 Welcome to MegaGrok! Use /growmygrok to gain XP and evolve your Grok.\n"
                 "Use /help to see commands."
                 )


@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🐸 *MegaGrok Bot Commands*\n\n"
        "/start - Begin your MegaGrok journey.\n"
        "/growmygrok - Feed your MegaGrok cosmic hop-energy! Gain XP and evolve.\n"
        "/hop - Perform the Hop Ritual for extra XP (once per day).\n"
        "/fight - Battle a FUDling for XP rewards.\n"
        "/profile - View your MegaGrok profile card (image).\n"
        "/leaderboard - See top 10 trainers.\n"
        "/help - Show this menu.\n\n"
        "✨ Level up, complete quests, and evolve your MegaGrok into legendary forms!"
    )
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['growmygrok'])
def grow_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or str(user_id)
    get_user(user_id, username)
    xp_gain = random.randint(-10, 30)  # leave some risk/reward
    new_xp, new_level, new_form = add_xp(user_id, xp_gain)
    # build progress
    level = new_level
    current_level_xp = (level - 1) * 200
    next_level_xp = level * 200
    xp_into_level = new_xp - current_level_xp
    xp_needed = max(next_level_xp - current_level_xp, 1)
    progress_blocks = int((xp_into_level / xp_needed) * 10)
    progress_bar = "[" + "█" * progress_blocks + "-" * (10 - progress_blocks) + "]"
    bot.reply_to(message,
                 f"✨ Your MegaGrok grows! {xp_gain:+} XP\n"
                 f"Level: {level}\n"
                 f"XP: {xp_into_level}/{xp_needed}\n"
                 f"Progress: {progress_bar}"
                 )


@bot.message_handler(commands=['hop'])
def hop_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or str(user_id)
    get_user(user_id, username)
    quests = get_quests(user_id)
    if quests["hop"] == 1:
        bot.reply_to(message, "🐸 You've already done your Hop Ritual today!")
        return
    xp_gain = random.randint(20, 50)
    add_xp(user_id, xp_gain)
    cursor.execute("UPDATE daily_quests SET quest_hop = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    bot.reply_to(message,
                 f"🐸✨ Hop Ritual complete! +{xp_gain} XP\n"
                 f"You can use /hop once per day."
                 )


@bot.message_handler(commands=['fight'])
def fight_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or str(user_id)
    get_user(user_id, username)
    quests = get_quests(user_id)
    if quests["fight"] == 1:
        bot.reply_to(message, "⚔️ You've already fought a FUDling today!")
        return
    win = random.choice([True, False])
    if win:
        xp = random.randint(50, 150)
        bot.reply_to(message, f"⚡🐸 You defeated a FUDling! +{xp} XP")
    else:
        xp = random.randint(10, 20)
        bot.reply_to(message, f"😵 You slipped but still gained wisdom. +{xp} XP")
    add_xp(user_id, xp)
    cursor.execute("UPDATE daily_quests SET quest_fight = 1 WHERE user_id = ?", (user_id,))
    conn.commit()


@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or str(user_id)
    user = get_user(user_id, username)
    xp = user["xp"]
    level = max(user["level"], 1)
    form = user["form"] or evolve(level)
    try:
        img_path = generate_profile_card(user_id, username, xp, level, form)
        with open(img_path, "rb") as f:
            bot.send_photo(message.chat.id, f)
    except Exception as e:
        bot.reply_to(message, f"Could not generate profile image: {e}")


@bot.message_handler(commands=['leaderboard'])
def leaderboard_command(message):
    cursor.execute("SELECT username, xp FROM users ORDER BY xp DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        bot.reply_to(message, "No players yet. Be the first to /growmygrok!")
        return
    text_lines = ["🏆 MegaGrok Leaderboard\n"]
    rank = 1
    for username, xp in rows:
        display = username if username else "anonymous"
        text_lines.append(f"{rank}. @{display} — {xp} XP")
        rank += 1
    bot.reply_to(message, "\n".join(text_lines))


# -------------------------
# Start Bot (entrypoint)
# -------------------------

if __name__ == "__main__":
    print("Starting MegaGrok bot (polling).")
    # NOTE: Deploy as a Background Worker on Render so polling doesn't conflict
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
