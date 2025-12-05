# bot/images.py
# ------------------------------------------------------------------
# IMAGE GENERATION UTILITIES FOR MEGAGROK RPG
# Profile Cards, Leaderboard Posters, and Future Generators
# ------------------------------------------------------------------

import os
import time
from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------------
# PROFILE IMAGE GENERATOR (your existing code, preserved)
# ------------------------------------------------------------------

def generate_profile_image(user_payload):
    """
    Existing profile image generator.
    You can upgrade this later with evolution icons, comic borders,
    stats, etc.
    """
    user_id = user_payload["user_id"]
    username = user_payload.get("username", f"User{user_id}")
    level = user_payload.get("level", 1)
    xp_total = user_payload.get("xp_total", 0)

    # simple placeholder canvas
    W, H = 900, 1100
    img = Image.new("RGB", (W, H), (18, 18, 24))
    draw = ImageDraw.Draw(img)

    # fonts
    try:
        font_title = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 80)
        font_text = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 50)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((50, 50), "MEGAGROK PROFILE", fill=(255, 150, 50), font=font_title)
    draw.text((50, 200), f"User: {username}", fill=(100, 255, 255), font=font_text)
    draw.text((50, 300), f"Level: {level}", fill=(255, 200, 80), font=font_text)
    draw.text((50, 400), f"XP Total: {xp_total}", fill=(255, 200, 80), font=font_text)

    out_path = f"/tmp/profile_{user_id}_{int(time.time())}.png"
    img.save(out_path, "PNG")
    return out_path


# ------------------------------------------------------------------
# LEADERBOARD IMAGE GENERATOR (old v1 kept as fallback)
# ------------------------------------------------------------------

def generate_leaderboard_image():
    """
    Existing leaderboard (simple version).
    Kept for fallback/compatibility.
    """
    W, H = 900, 1400
    img = Image.new("RGB", (W, H), (24, 24, 30))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 80)
        font_text = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 45)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((40, 40), "MEGAGROK LEADERBOARD (v1)", fill=(255, 120, 50), font=font_title)

    from bot.db import get_top_users
    rows = get_top_users(5)

    y = 180
    for idx, row in enumerate(rows, start=1):
        line = f"#{idx}  {row['username']} — {row['xp_total']} XP"
        draw.text((60, y), line, fill=(100, 255, 255), font=font_text)
        y += 100

    out_path = f"/tmp/leaderboard_v1_{int(time.time())}.png"
    img.save(out_path, "PNG")
    return out_path


# ------------------------------------------------------------------
# LEADERBOARD POSTER v2 — COMIC STYLE (new recommended version)
# ------------------------------------------------------------------

def generate_leaderboard_poster_v2(entries, limit=10):
    """
    entries: list of dicts from db.get_top_users(limit)
    Output: High-quality comic-style leaderboard poster.
    """

    # Canvas size
    W, H = 900, 1400
    img = Image.new("RGB", (W, H), (18, 18, 24))
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        title_font = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 90)
        row_font = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 48)
        small_font = ImageFont.truetype("assets/fonts/megagrok_bold.ttf", 32)
    except:
        title_font = ImageFont.load_default()
        row_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Title
    title_text = "MEGAGROK\nLEADERBOARD"
    draw.multiline_text(
        (60, 60),
        title_text,
        fill=(255, 140, 40),
        font=title_font,
        spacing=10
    )

    # Rank badge colors
    rank_colors = {
        1: (255, 215, 0),   # gold
        2: (192, 192, 192), # silver
        3: (205, 127, 50),  # bronze
        # all others red-ish
    }

    y = 300
    gap = 25

    for idx, entry in enumerate(entries[:limit], start=1):

        username = entry["username"]
        xp = entry["xp_total"] if "xp_total" in entry else entry.get("xp", 0)

        # Circle badge
        r = 60
        badge_color = rank_colors.get(idx, (255, 60, 60))

        draw.ellipse(
            (60, y, 60 + r, y + r),
            fill=badge_color,
            outline=(0, 0, 0),
            width=4
        )

        # Rank number inside badge
        draw.text(
            (60 + 18, y + 4),
            str(idx),
            font=row_font,
            fill=(0, 0, 0)
        )

        # Username
        draw.text(
            (160, y),
            username,
            font=row_font,
            fill=(100, 255, 255)
        )

        # XP text
        draw.text(
            (160, y + 55),
            f"{xp} XP",
            font=small_font,
            fill=(255, 200, 80)
        )

        y += 130 + gap

    out_path = f"/tmp/leaderboard_v2_{int(time.time())}.png"
    img.save(out_path, "PNG")

    return out_path
