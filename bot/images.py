# bot/images.py
# MegaGrok Leaderboard Renderer — Comic Style Premium Edition

import os
import math               # << REQUIRED for medal burst!
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "assets/fonts/megagrok.ttf"
DEFAULT_FONT = "DejaVuSans-Bold.ttf"

# --------------------------------------------------------
# FONT LOADING
# --------------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
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
    for dx in range(-width, width+1):
        for dy in range(-width, width+1):
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
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
        return  # no medal for rank > 3

    # Burst explosion circle
    r = 32
    cx, cy = x + r, y + r

    pts = []
    for i in range(18):
        angle = i * 2 * math.pi / 18
        dist = r if i % 2 == 0 else r * 0.6
        pts.append((
            cx + dist * math.cos(angle),
            cy + dist * math.sin(angle)
        ))

    draw.polygon(pts, fill=color, outline="black")
    draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill="white", outline="black")

    fnt = load_font(28)
    txt = str(rank)
    tw, th = measure(draw, txt, fnt)
    draw.text((cx - tw/2, cy - th/2), txt, font=fnt, fill="black")

# --------------------------------------------------------
# LEADERBOARD GENERATOR (MAIN FUNCTION)
# --------------------------------------------------------
def generate_leaderboard_premium(users):
    """
    users = list of dicts:
      user_id, username, level, xp_total
    """

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), (22, 22, 22))
    dr = ImageDraw.Draw(img)

    # ---------- TITLE ----------
    title = "MEGAGROK LEADERBOARD"
    title_font = load_font(110)
    tw, th = measure(dr, title, title_font)
    draw_text_outline(
        dr,
        ((W - tw) // 2, 80),
        title,
        title_font,
        fill="#FFB545"
    )

    # ---------- HEADER LINE ----------
    dr.line((120, 240, W - 120, 240), fill="#FFB545", width=6)

    # ---------- ROW SETTINGS ----------
    start_y = 300
    row_h = 120

    name_font = load_font(58)
    stats_font = load_font(46)

    for idx, user in enumerate(users[:12]):
        y = start_y + idx * row_h

        rank = idx + 1
        uid = user.get("user_id")
        username = user.get("username") or f"User{uid}"
        level = user.get("level", 1)
        xp = user.get("xp_total", 0)

        # MEDAL FOR TOP 3
        if rank <= 3:
            draw_medal(dr, 120, y + 10, rank)
            name_x = 200
        else:
            # Draw rank number normally
            rank_text = f"{rank}."
            rtw, rth = measure(dr, rank_text, name_font)
            draw_text_outline(dr, (120, y + 25), rank_text, name_font, fill="white")
            name_x = 200

        # USERNAME
        draw_text_outline(dr, (name_x, y + 10), username, name_font, fill="#7EF2FF")

        # LEVEL + XP (right aligned)
        stats_text = f"LV {level} • {xp} XP"
        stw, sth = measure(dr, stats_text, stats_font)
        draw_text_outline(dr, (W - 160 - stw, y + 35), stats_text, stats_font, fill="#FFB545")

        # Row separator line
        dr.line((120, y + row_h - 10, W - 120, y + row_h - 10), fill="#303030", width=3)

    # ---------- FOOTER ----------
    footer = "MegaGrok Metaverse"
    ff = load_font(48)
    ftw, fth = measure(dr, footer, ff)
    draw_text_outline(dr, ((W-ftw)//2, H-160), footer, ff, fill="#777777")

    # Save
    out = "/tmp/leaderboard.jpg"
    img.save(out, quality=95)
    return out
