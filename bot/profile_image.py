# bot/profile_image.py
# Comic-style MegaGrok profile card generator
# Produces 1080 x 1350 PNG files in /tmp/
#
# Expected payload (dict) keys:
#   user_id (int)
#   username (str)
#   form (optional str) -> used to pick portrait: assets/mobs/{form}.png
#   portrait (optional str) -> explicit path to portrait image
#   level (int)
#   xp_total (int)
#   wins (int)
#   fights (int)
#   rituals (int)
#
# Usage:
#   path = generate_profile_image(payload)

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageColor
import os
import time
import math

# ---------------------- CONFIG ----------------------
CANVAS_W = 1080
CANVAS_H = 1350
OUTPUT_DIR = "/tmp"
DEFAULT_FONT_PATHS = [
    "/usr/local/share/fonts/megagrok.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]

FONT_TITLE_SIZE = 92
FONT_NAME_SIZE = 64
FONT_STATS_SIZE = 44
FONT_SMALL_SIZE = 34

ASSETS_MOBS = "assets/mobs"   # directory for portraits
FRAME_COLOR = (10, 10, 12)
BG_COLOR = (18, 18, 24)
TITLE_COLOR = (255, 184, 77)     # gold/orange
USERNAME_COLOR = (142, 240, 255) # neon cyan
STAT_COLOR = (255, 184, 77)
ACCENT_COLOR = (255, 120, 90)

# ---------------------- HELPERS ----------------------
def _find_font(preferred_paths=DEFAULT_FONT_PATHS, size=40):
    for p in preferred_paths:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()

def _load_font(size):
    # return a truetype or fallback font for that size
    for p in DEFAULT_FONT_PATHS:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()

def _text_size(draw, text, font):
    # uses textbbox for reliable measurement
    bbox = draw.textbbox((0,0), text, font=font)
    return (bbox[2]-bbox[0], bbox[3]-bbox[1])

def draw_text_outline(draw, pos, text, font, fill, outline_color=(0,0,0), outline_width=2):
    x, y = pos
    # draw outline by offsets
    for ox in range(-outline_width, outline_width+1):
        for oy in range(-outline_width, outline_width+1):
            if ox == 0 and oy == 0:
                continue
            draw.text((x+ox, y+oy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill)

def _halftone_overlay(size, spacing=16, radius=1, color=(255,255,255,8)):
    w, h = size
    layer = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    for yy in range(0, h, spacing):
        for xx in range(0, w, spacing):
            d.ellipse((xx-radius, yy-radius, xx+radius, yy+radius), fill=color)
    return layer.filter(ImageFilter.GaussianBlur(0.2))

def _rounded_rect(draw, box, radius, fill):
    # Pillow's rounded_rectangle exists; use it when available
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill)
    except Exception:
        # fallback: simple rectangle
        draw.rectangle(box, fill=fill)

def _safe_open_image(path, fallback_color=(60,60,60), size=None):
    try:
        if not path:
            raise FileNotFoundError
        img = Image.open(path).convert("RGBA")
        if size:
            img = ImageOps.contain(img, size)
        return img
    except Exception:
        # placeholder
        w = size[0] if size else 400
        h = size[1] if size else 400
        placeholder = Image.new("RGBA", (w,h), fallback_color + (255,))
        return placeholder

# ---------------------- GENERATOR ----------------------
def generate_profile_image(payload: dict) -> str:
    """
    Generate a comic-style profile image and return the path.
    payload must include user_id and username; other fields optional.
    """

    user_id = payload.get("user_id", int(time.time()))
    username = payload.get("username") or f"User{user_id}"
    level = int(payload.get("level", payload.get("lvl", 1) or 1))
    xp = int(payload.get("xp_total", payload.get("xp", 0) or 0))
    wins = int(payload.get("wins", 0) or 0)
    fights = int(payload.get("fights", payload.get("mobs_defeated", 0) or 0))
    rituals = int(payload.get("rituals", 0) or 0)

    # choose portrait: explicit portrait path preferred -> form -> default
    portrait_path = payload.get("portrait")
    if not portrait_path:
        form = payload.get("form")
        if form:
            candidate = os.path.join(ASSETS_MOBS, f"{form.lower()}.png")
            if os.path.exists(candidate):
                portrait_path = candidate
    if not portrait_path:
        # try username-based fallback
        fallback = os.path.join(ASSETS_MOBS, "default.png")
        portrait_path = fallback if os.path.exists(fallback) else None

    # fonts
    font_title = _load_font(FONT_TITLE_SIZE)
    font_name = _load_font(FONT_NAME_SIZE)
    font_stats = _load_font(FONT_STATS_SIZE)
    font_small = _load_font(FONT_SMALL_SIZE)

    # canvas
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG_COLOR + (255,))
    draw = ImageDraw.Draw(canvas)

    # subtle vignette / paper texture
    vignette = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    vd = ImageDraw.Draw(vignette)
    vd.ellipse((-CANVAS_W*0.2, -CANVAS_H*0.2, CANVAS_W*1.2, CANVAS_H*1.2), fill=(0,0,0,30))
    canvas = Image.alpha_composite(canvas, vignette)

    # halftone overlay
    try:
        ht = _halftone_overlay((CANVAS_W, CANVAS_H), spacing=18, radius=1, color=(255,255,255,6))
        canvas = Image.alpha_composite(canvas, ht)
    except Exception:
        pass

    draw = ImageDraw.Draw(canvas)

    # border/frame
    pad = 28
    border_box = (pad, pad, CANVAS_W - pad, CANVAS_H - pad)
    _rounded_rect(draw, border_box, radius=28, fill=None)
    # thick outer border via drawing rounded rect stroke (simulate)
    outline = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0,0,0,0))
    od = ImageDraw.Draw(outline)
    od.rounded_rectangle(border_box, radius=28, outline=FRAME_COLOR, width=8)
    canvas = Image.alpha_composite(canvas, outline)
    draw = ImageDraw.Draw(canvas)

    # Title (top)
    title_text = "MEGAGROK PROFILE"
    t_w, t_h = _text_size(draw, title_text, font_title)
    tx = (CANVAS_W - t_w) // 2
    ty = 44
    # drop shadow
    draw.text((tx + 6, ty + 6), title_text, font=font_title, fill=(0,0,0))
    draw.text((tx, ty), title_text, font=font_title, fill=TITLE_COLOR)

    # Portrait area (left / center)
    portrait_box_w = 640
    portrait_box_h = 640
    portrait_x = 80
    portrait_y = 160

    # draw portrait panel with white rounded mask
    panel = Image.new("RGBA", (portrait_box_w, portrait_box_h), (255,255,255,255))
    pmask = Image.new("L", (portrait_box_w, portrait_box_h), 0)
    pd = ImageDraw.Draw(pmask)
    pd.rounded_rectangle((0,0,portrait_box_w,portrait_box_h), radius=28, fill=255)
    # Add darker frame behind panel
    shadow = Image.new("RGBA", (portrait_box_w+20, portrait_box_h+20), (0,0,0,60))
    canvas.paste(shadow, (portrait_x-10, portrait_y-10), shadow)
    canvas.paste(panel, (portrait_x, portrait_y), pmask)

    # open portrait
    portrait_img = _safe_open_image(portrait_path, fallback_color=(80,80,90), size=(portrait_box_w-40, portrait_box_h-40))
    # center portrait in panel (with small inner padding)
    pw, ph = portrait_img.size
    paste_x = portrait_x + (portrait_box_w - pw)//2
    paste_y = portrait_y + (portrait_box_h - ph)//2
    canvas.paste(portrait_img, (paste_x, paste_y), portrait_img)

    draw = ImageDraw.Draw(canvas)

    # Username label to the right of portrait
    name_x = portrait_x + portrait_box_w + 48
    name_y = portrait_y + 20
    uname = username if username else f"User{user_id}"
    # outlined username
    draw_text_outline(draw, (name_x, name_y), uname, font_name, fill=USERNAME_COLOR, outline_color=(0,0,0), outline_width=3)

    # Level and XP line under username: LV 23 • 149 XP
    lvlxp_text = f"LV {int(level)} \u2022 {int(xp)} XP"
    sx, sy = _text_size(draw, lvlxp_text, font_stats)
    stats_y = name_y + _text_size(draw, uname, font_name)[1] + 18
    # draw gold stats with slight shadow
    draw.text((name_x+2, stats_y+2), lvlxp_text, font=font_stats, fill=(0,0,0))
    draw.text((name_x, stats_y), lvlxp_text, font=font_stats, fill=STAT_COLOR)

    # XP progress bar (under LV•XP)
    # we need xp_current and xp_to_next to paint progress; if payload has xp_current and xp_to_next use them, otherwise estimate progress using xp and level.
    xp_current = payload.get("xp_current")
    xp_to_next = payload.get("xp_to_next_level")
    if xp_current is None or xp_to_next is None:
        # try to estimate: create progress within 0..1 based on level only
        # if user provided xp_total only, we cannot accurately compute; show partial filled bar from 0..min(1, (xp % next) / next) naive approach
        xp_current = payload.get("xp_current", payload.get("xp", 0) % 100)
        xp_to_next = payload.get("xp_to_next_level", payload.get("xp_to_next_level", 100))
    try:
        pct = max(0.0, min(1.0, float(xp_current) / float(xp_to_next))) if xp_to_next else 0.0
    except Exception:
        pct = 0.0

    bar_w = 300
    bar_h = 28
    bar_x = name_x
    bar_y = stats_y + sy + 18
    # background
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=14, fill=(30,30,30))
    # fill
    fill_w = int(bar_w * pct)
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=14, fill=TITLE_COLOR)
    # percent text
    pct_text = f"{int(pct * 100)}%"
    tw, th = _text_size(draw, pct_text, font_small)
    draw.text((bar_x + bar_w + 12, bar_y + (bar_h - th)//2), pct_text, font=font_small, fill=(200,200,200))

    # Small stats tiles (wins, fights, rituals) below portrait
    tile_w = 280
    tile_h = 110
    tile_pad = 28
    first_tile_x = portrait_x
    first_tile_y = portrait_y + portrait_box_h + 34

    tiles = [
        ("WINS", wins),
        ("FIGHTS", fights),
        ("RITUALS", rituals)
    ]
    tx = first_tile_x
    ty = first_tile_y
    for title, val in tiles:
        # tile background
        draw.rounded_rectangle([tx, ty, tx + tile_w, ty + tile_h], radius=18, fill=(22,22,30))
        # title
        ttw, tth = _text_size(draw, title, font_small)
        draw.text((tx + 18, ty + 12), title, font=font_small, fill=(180,180,180))
        # value big
        vtxt = str(val)
        vtw, vth = _text_size(draw, vtxt, font_stats)
        draw.text((tx + tile_w - 18 - vtw, ty + (tile_h - vth)//2), vtxt, font=font_stats, fill=TITLE_COLOR)
        tx += tile_w + tile_pad

    # footer / tagline
    footer = "MegaGrok Metaverse"
    ftw, fth = _text_size(draw, footer, font_small)
    draw.text(((CANVAS_W - ftw)//2, CANVAS_H - 80), footer, font=font_small, fill=(110,110,110))

    # small comic accent: draw a jagged "burst" behind portrait top-left corner (decorative)
    # simple burst: polygon
    bx = portrait_x + 40
    by = portrait_y - 40
    burst_pts = []
    R = 36
    spikes = 8
    for i in range(spikes*2):
        angle = i * math.pi * 2 / (spikes*2)
        r = R if i % 2 == 0 else R/2
        burst_pts.append((bx + math.cos(angle)*r, by + math.sin(angle)*r))
    draw.polygon(burst_pts, fill=ACCENT_COLOR)

    # finalize: convert to RGB and save
    out_name = f"profile_{user_id}_{int(time.time())}.png"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    try:
        canvas_rgb = canvas.convert("RGB")
        canvas_rgb.save(out_path, quality=90)
    except Exception:
        # fallback: use /tmp path
        out_path = os.path.join("/tmp", out_name)
        canvas.convert("RGB").save(out_path, quality=90)

    return out_path
