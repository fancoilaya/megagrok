# bot/images.py
# FINAL Leaderboard Renderer (Compatible With DB dict output)

import os
import math
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "assets/fonts/megagrok.ttf"
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# --------------------------------------------------
# FONT LOADING
# --------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.truetype(FALLBACK_FONT, size)


# --------------------------------------------------
# TEXT MEASUREMENT
# --------------------------------------------------
def measure(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return (box[2] - box[0], box[3] - box[1])


# --------------------------------------------------
# OUTLINE TEXT
# --------------------------------------------------
def draw_text_outline(draw, xy, text, font, fill, outline="black", width=3):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


# --------------------------------------------------
# COMIC MEDALS FOR TOP 3
# --------------------------------------------------
def draw_medal(draw, x, y, rank):
    colors = {
        1: "#ffd700",  # Gold
        2: "#c0c0c0",  # Silver
        3: "#cd7f32",  # Bronze
    }
    if rank not in colors:
        return

    color = colors[rank]
    r = 28
    cx, cy = x + r, y + r

    # burst background
    pts = []
    for i in range(18):
        ang = i * (math.pi * 2 / 18)
        dist = r if i % 2 == 0 else r * 0.55
        pts.append((cx + dist * math.cos(ang), cy + dist * math.sin(ang)))
    draw.polygon(pts, fill=color, outline="black")

    # center circle
    draw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill="white", outline="black")

    # rank text
    fnt = load_font(26)
    tw, th = measure(draw, str(rank), fnt)
    draw.text((cx - tw / 2, cy - th / 2), str(rank), font=fnt, fill="black")


# --------------------------------------------------
# LEADERBOARD GENERATOR (DICT COMPATIBLE)
# --------------------------------------------------
def generate_leaderboard_premium(users):
    """
    users = list of dicts from db.get_top_users()
    Required fields:
      user_id, username, xp_total, level
    """

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#1c1c1e")
    dr = ImageDraw.Draw(img)

    # ---------- TITLE (2-line centered) ----------
    title = "MEGAGROK\nLEADERBOARD"
    tfont = load_font(120)
    tb = dr.multiline_textbbox((0, 0), title, font=tfont, align="center")
    tw = tb[2] - tb[0]
    draw_text_outline(dr, ((W - tw) // 2, 70), title, tfont, fill="#ffbb55", width=4)

    # ---------- START AREA ----------
    y = 330
    row_h = 130

    name_font = load_font(60)
    stats_font = load_font(44)

    for idx, user in enumerate(users[:12]):
        rank = idx + 1
        username = user.get("username") or f"User{user['user_id']}"
        xp = user.get("xp_total", 0)
        level = user.get("level", 1)

        # ------------ Medal or Rank Number ------------
        if rank <= 3:
            draw_medal(dr, 120, y + 10, rank)
            name_x = 220
        else:
            draw_text_outline(dr, (120, y + 20), f"{rank}.", name_font, fill="white")
            name_x = 220

        # ------------ Username ------------
        draw_text_outline(dr, (name_x, y), username, name_font, fill="#7EF2FF")

        # ------------ Level + XP (right aligned) ------------
        stats = f"LV {level}  •  {xp} XP"
        stw, sth = measure(dr, stats, stats_font)
        draw_text_outline(dr, (W - 140 - stw, y + 35), stats, stats_font, fill="#FFB545")

        # ------------ Separator Line ------------
        dr.line((120, y + row_h - 10, W - 120, y + row_h - 10), fill="#2e2e2e", width=3)

        y += row_h

    # --------- FOOTER ----------
    footer = "MegaGrok Metaverse"
    ff = load_font(42)
    ftw, fth = measure(dr, footer, ff)
    draw_text_outline(dr, ((W - ftw) // 2, H - 150), footer, ff, fill="#777777")

    out = "/tmp/leaderboard.jpg"
    img.save(out, quality=95)
    return out
