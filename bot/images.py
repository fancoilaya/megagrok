# bot/images.py
# ------------------------------------------------------------
# MegaGrok Comic-Style Leaderboard Poster Generator
# ------------------------------------------------------------

from PIL import Image, ImageDraw, ImageFont
import os
import time
from typing import List, Dict

CANVAS_W = 1080
CANVAS_H = 1920

# Font search locations
FONT_PATHS = [
    "assets/fonts/megagrok_bold.ttf",
    "/var/data/megagrok_bold.ttf",
]

def _load_font(size: int):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()

# Colors
COLOR_TITLE = (255, 159, 28)
COLOR_USERNAME = (110, 231, 249)
COLOR_BADGE = (255, 209, 102)
COLOR_XP = (255, 244, 230)
OUTLINE = (20, 12, 40)
SHADOW = (0, 0, 0, 180)

def _draw_text(draw, x, y, text, font, fill, outline, shadow=True):
    if shadow:
        draw.text((x+4, y+4), text, font=font, fill=(0,0,0))
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)

def _create_gradient():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (10, 6, 20))
    px = img.load()
    for y in range(CANVAS_H):
        f = y / CANVAS_H
        r = int(10 * (1 - f) + 24 * f)
        g = int(6 * (1 - f) + 6 * f)
        b = int(20 * (1 - f) + 46 * f)
        for x in range(CANVAS_W):
            px[x,y] = (r,g,b)
    return img

def generate_leaderboard_poster_v2(rows: List[Dict], limit: int = 10):
    rows = rows[:limit]
    while len(rows) < 10:
        rows.append({"username": "Unknown", "xp_total": 0, "level": 1})

    bg = _create_gradient()
    draw = ImageDraw.Draw(bg)

    title_font = _load_font(110)
    row_font = _load_font(60)
    xp_font = _load_font(40)
    lvl_font = _load_font(32)

    # Title
    txt = "MEGAGROK\nLEADERBOARD"
    y = 80
    for line in txt.split("\n"):
        w, h = draw.textsize(line, font=title_font)
        x = (CANVAS_W - w)//2
        _draw_text(draw, x, y, line, title_font, COLOR_TITLE, OUTLINE)
        y += h + 5

    start_y = y + 50
    row_height = 120

    for i, entry in enumerate(rows):
        row_y = start_y + i * row_height

        # rank badge
        cx, cy = 140, row_y + 50
        r = 40
        draw.ellipse((cx-r,cy-r,cx+r,cy+r), fill=COLOR_BADGE, outline=(0,0,0), width=4)
        rn = str(i+1)
        rw, rh = draw.textsize(rn, font=row_font)
        draw.text((cx-rw/2,cy-rh/2), rn, font=row_font, fill=(0,0,0))

        # username
        username = entry.get("username","Unknown")
        _draw_text(draw, 240, row_y, username, row_font, COLOR_USERNAME, OUTLINE)

        # XP
        xp = f"{entry.get('xp_total', 0)} XP"
        xpw, _ = draw.textsize(xp, font=xp_font)
        _draw_text(draw, CANVAS_W - xpw - 80, row_y+40, xp, xp_font, COLOR_XP, OUTLINE)

        # level
        lvl = f"LV {entry.get('level',1)}"
        draw.text((240, row_y+70), lvl, font=lvl_font, fill=(255,220,150))

    # save to disk
    out_path = f"/var/data/leaderboard_{int(time.time())}.png"
    try:
        bg.save(out_path, "PNG")
        return out_path
    except:
        fallback = f"/tmp/leaderboard_{int(time.time())}.png"
        bg.save(fallback, "PNG")
        return fallback
