# bot/images.py
# MegaGrok Leaderboard Renderer — Comic Style Premium Edition
# Updated to use Display Name instead of Username (Option A)

import os
import math
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "assets/fonts/megagrok.ttf"
DEFAULT_FONT = "DejaVuSans-Bold.ttf"


# --------------------------------------------------------
# FONT LOADING
# --------------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.truetype(DEFAULT_FONT, size)


# --------------------------------------------------------
# SAFE TEXT SIZE
# --------------------------------------------------------
def measure(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return (box[2] - box[0], box[3] - box[1])


# --------------------------------------------------------
# OUTLINE TEXT DRAWING
# --------------------------------------------------------
def draw_text_outline(draw, xy, text, font, fill, outline="black", width=3):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


# --------------------------------------------------------
# COMIC MEDAL BADGES FOR TOP 3
# --------------------------------------------------------
def draw_medal(draw, x, y, rank):
    if rank == 1:
        color = "#FFD700"  # Gold
    elif rank == 2:
        color = "#C0C0C0"  # Silver
    elif rank == 3:
        color = "#CD7F32"  # Bronze
    else:
        return

    r = 32
    cx, cy = x + r, y + r

    pts = []
    for i in range(18):
        angle = i * math.pi * 2 / 18
        dist = r if i % 2 == 0 else r * 0.6
        pts.append((cx + dist * math.cos(angle), cy + dist * math.sin(angle)))

    draw.polygon(pts, fill=color, outline="black")
    draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill="white", outline="black")

    fnt = load_font(28)
    txt = str(rank)
    tw, th = measure(draw, txt, fnt)
    draw.text((cx - tw / 2, cy - th / 2), txt, font=fnt, fill="black")


# --------------------------------------------------------
# LEADERBOARD GENERATOR (MAIN FUNCTION)
# --------------------------------------------------------
def generate_leaderboard_premium(users):
    """
    EXPECTED user dict fields:
      display_name   (string or None)
      username       (@username, string or None)
      xp_total
      level
    """

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), (22, 22, 22))
    dr = ImageDraw.Draw(img)

    # ---------- TITLE ----------
    title = "MEGAGROK\nLEADERBOARD"
    title_font = load_font(120)

    for i, line in enumerate(title.split("\n")):
        tw, th = measure(dr, line, title_font)
        draw_text_outline(
            dr,
            ((W - tw) // 2, 80 + i * 120),
            line,
            title_font,
            fill="#FFB545"
        )

    # ---------- ROW SETTINGS ----------
    start_y = 350
    row_h = 150

    name_font = load_font(64)
    stats_font = load_font(48)

    for idx, user in enumerate(users[:12]):
        y = start_y + idx * row_h

        rank = idx + 1
        user_id = user.get("user_id")

        # ⭐ DISPLAY NAME PRIORITY (Option A):
        # 1. display_name
        # 2. username
        # 3. fallback User123
        display_name = (
            user.get("display_name")
            or user.get("username")
            or f"User{user_id}"
        )

        level = user.get("level", 1)
        xp = user.get("xp_total", 0)

        # --- Medal or Rank Number ---
        if rank <= 3:
            draw_medal(dr, 120, y + 10, rank)
            name_x = 220
        else:
            rank_text = f"{rank}."
            draw_text_outline(dr, (120, y + 20), rank_text, name_font, fill="white")
            name_x = 220

        # --- Display Name (line 1) ---
        draw_text_outline(dr, (name_x, y), display_name, name_font, fill="#7EF2FF")

        # --- Stats under name (line 2) ---
        stats = f"LV {level} • {xp} XP"
        draw_text_outline(dr, (name_x, y + 65), stats, stats_font, fill="#FFB545")

        # Row divider
        dr.line((120, y + row_h - 10, W - 120, y + row_h - 10), fill="#303030", width=3)

    # ---------- FOOTER ----------
    footer = "MegaGrok Metaverse"
    ff = load_font(48)
    ftw, fth = measure(dr, footer, ff)
    draw_text_outline(dr, ((W - ftw) // 2, H - 150), footer, ff, fill="#777777")

    # Save final image
    out = "/tmp/leaderboard.jpg"
    img.save(out, quality=95)
    return out
