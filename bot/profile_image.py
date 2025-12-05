# bot/profile_image.py
# MEGAGROK PROFILE CARD v3 — Comic Halftone Edition (fixed title placement)

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Prefer your custom font in assets, but fall back if unavailable
FONT_CANDIDATES = [
    "assets/fonts/megagrok.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

def load_font_safe(size):
    """
    Try several font files. Return a PIL ImageFont instance.
    """
    for p in FONT_CANDIDATES:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    # As a last resort, use the default PIL font (very small), then scale via transform
    return ImageFont.load_default()

# small helper to measure text using modern Pillow API
def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])

# outline-style text (draw black outlines then fill)
def draw_outline(draw, xy, text, font, fill, outline=(0,0,0), w=3):
    x, y = xy
    # outline ring
    for dx in range(-w, w+1):
        for dy in range(-w, w+1):
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)

# generate a halftone-like explosion background for the portrait
def generate_halftone(stage, size=(220,220)):
    w, h = size
    base = Image.new("RGB", size, (40,40,40))
    dr = ImageDraw.Draw(base)

    COLORS = {
        1: ("#33FF55", "#0A5015"),
        2: ("#35D1FF", "#0A3045"),
        3: ("#FF8A00", "#451F00"),
        4: ("#A243FF", "#2A0045"),
        5: ("#FFD93D", "#4D3B00"),
    }

    c1, c2 = COLORS.get(stage, COLORS[1])

    # radial burst lines
    for i in range(24):
        angle = (i / 24) * math.tau
        x = w/2 + math.cos(angle) * w
        y = h/2 + math.sin(angle) * h
        dr.line((w/2, h/2, x, y), fill=c1, width=3)

    # halftone dots pattern
    for yy in range(0, h, 10):
        for xx in range(0, w, 10):
            if (xx + yy) % 20 == 0:
                dr.ellipse((xx, yy, xx+6, yy+6), fill=c2)

    return base.filter(ImageFilter.GaussianBlur(1.5))

# rank burst badge
def draw_rank_badge(draw, rank, x, y):
    if not rank:
        return
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    col = colors[rank-1] if rank <= 3 else "#3A3A3A"

    burst_r = 32
    cx, cy = x+burst_r, y+burst_r

    pts = []
    for i in range(16):
        ang = i * math.pi*2/16
        r = burst_r if i%2==0 else burst_r*0.6
        pts.append((cx+math.cos(ang)*r, cy+math.sin(ang)*r))

    draw.polygon(pts, fill=col, outline="black")
    draw.ellipse((cx-18, cy-18, cx+18, cy+18), fill="white", outline="black")

    fnt = load_font_safe(28)
    txt = str(rank)
    tw, th = text_size(draw, txt, fnt)
    draw.text((cx-tw/2, cy-th/2), txt, font=fnt, fill="black")

# main profile generator (returns /tmp path)
def generate_profile_image(payload):
    user_id = payload["user_id"]
    username = payload.get("username", f"User{user_id}")
    level = payload.get("level", 1)
    xp_total = payload.get("xp_total", 0)
    wins = payload.get("wins", 0) or 0
    fights = payload.get("fights", 0) or 0
    rituals = payload.get("rituals", 0) or 0
    stage = int(payload.get("form", 1) or 1)
    rank = payload.get("rank", None)
    xp_to_next = payload.get("xp_to_next", max(100, level*100))

    # canvas
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), (20,20,20))
    dr = ImageDraw.Draw(img)

    # ---------- TITLE layout: dynamic safe top margin ----------
    TITLE_TEXT = "MEGAGROK PROFILE"
    TITLE_SIZE = 96   # slightly reduced from 120 for safety
    title_font = load_font_safe(TITLE_SIZE)

    # compute font ascent/height and set top margin to accomodate
    # use textbbox to ensure accurate metrics
    ttw, tth = text_size(dr, TITLE_TEXT, title_font)
    # give some extra padding above
    TOP_MARGIN = max(48, int(title_font.size * 0.6))

    # center title horizontally at TOP_MARGIN
    title_x = (W - ttw) // 2
    title_y = TOP_MARGIN

    draw_outline(dr, (title_x, title_y), TITLE_TEXT, title_font, fill="#FFB545", outline=(8,6,4), w=3)

    # rank badge (top-right)
    draw_rank_badge(dr, rank, W - 240, title_y)

    # ---------- Portrait frame and halftone -->
    px, py = 120, title_y + tth + 40   # place portrait under the title with spacing
    pw, ph = 220, 220
    # outer white frame
    draw_round_rect = getattr(ImageDraw.Draw(img), "rounded_rectangle", None)
    if draw_round_rect:
        dr.rounded_rectangle((px-10, py-10, px+pw+10, py+ph+10), fill=(255,255,255), radius=14)
    else:
        dr.rectangle((px-10, py-10, px+pw+10, py+ph+10), fill=(255,255,255))
    # halftone portrait background
    halo = generate_halftone(stage, size=(pw, ph))
    img.paste(halo, (px, py))

    # ---------- Username + level + xp ----------
    name_font = load_font_safe(64)
    lv_font = load_font_safe(42)

    nx = px + pw + 80
    ny = py + 10

    draw_outline(dr, (nx, ny), username, name_font, fill="#7EF2FF", outline=(0,0,0), w=3)

    lv_text = f"LV {level} • {xp_total} XP"
    draw_outline(dr, (nx, ny + 80), lv_text, lv_font, fill="#FFB545", outline=(0,0,0), w=2)

    # XP bar
    bar_x = nx
    bar_y = ny + 140
    bar_w = 520
    bar_h = 34
    dr.rounded_rectangle((bar_x, bar_y, bar_x+bar_w, bar_y+bar_h), fill="#333333", radius=20)
    pct = min(1.0, xp_total / max(1, xp_to_next))
    fill_w = int(bar_w * pct)
    if fill_w > 0:
        dr.rounded_rectangle((bar_x, bar_y, bar_x+fill_w, bar_y+bar_h), fill="#7EF2FF", radius=20)

    # ---------- Stat tiles (WINS, FIGHTS, RITUALS, POWER) ----------
    tile_y = py + ph + 150
    tile_w = 240
    tile_h = 140
    gap = 28

    stats = [
        ("WINS", wins),
        ("FIGHTS", fights),
        ("RITUALS", rituals),
        ("POWER", max(1, level * 5 + wins * 2)),
    ]

    tile_font_label = load_font_safe(36)
    tile_font_num = load_font_safe(56)

    total_width = 4*tile_w + 3*gap
    x0 = (W - total_width) // 2

    for i, (label, val) in enumerate(stats):
        tx = x0 + i*(tile_w + gap)
        # tile background with border
        dr.rounded_rectangle((tx, tile_y, tx+tile_w, tile_y+tile_h), fill="#1E1E1E", radius=20, outline="#FFB545", width=3)
        # label (top)
        lw, lh = text_size(dr, label, tile_font_label)
        draw_outline(dr, (tx + (tile_w - lw)//2, tile_y + 12), label, tile_font_label, fill="white", outline=(0,0,0), w=2)
        # value (center)
        val_s = str(val)
        vw, vh = text_size(dr, val_s, tile_font_num)
        draw_outline(dr, (tx + (tile_w - vw)//2, tile_y + 58), val_s, tile_font_num, fill="#FFB545", outline=(0,0,0), w=3)

    # ---------- Footer ----------
    foot_font = load_font_safe(44)
    footer = "MegaGrok Metaverse"
    fw, fh = text_size(dr, footer, foot_font)
    draw_outline(dr, ((W - fw)//2, H - 140), footer, foot_font, fill="#777777", outline=(0,0,0), w=2)

    # ---------- Save file ----------
    out_path = f"/tmp/profile_{user_id}.jpg"
    try:
        img.save(out_path, quality=95)
    except Exception:
        # fallback to PNG if JPG fails
        out_path = f"/tmp/profile_{user_id}.png"
        img.save(out_path, "PNG")

    return out_path
