# bot/images.py
"""
Comic-cover style MegaGrok visuals.

Features:
- Comic-cover trading-card style profile generator (uses /mnt/data/Cover1.jpg as subtle paper texture if present)
- Comic-cover "Poster Page" leaderboard (single-page spread) showing top 10 as stylized panels
- Fog-free, retro halftone / paper texture, heavy outlines, energy bursts
- Safe font fallback (Roboto-Bold.ttf in assets/ if available)
"""

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# If you uploaded a reference cover (you did), use this path
COVER_REF_PATH = "/mnt/data/Cover1.jpg"

ASSET_DIR = "assets"


# -------------------------
# FONT LOADING (safe fallback)
# -------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()


TITLE_FONT = load_font(110)
BIG_TITLE_FONT = load_font(64)
HEADER_FONT = load_font(38)
NUM_FONT = load_font(46)
STAT_FONT = load_font(34)
SMALL_FONT = load_font(20)
BODY_FONT = load_font(24)


# -------------------------
# Helpers: text size safe
# -------------------------
def text_size(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        try:
            return font.getsize(text)
        except Exception:
            return (len(text) * 8, 16)


# -------------------------
# Outline text helper
# -------------------------
def outline_text(draw, pos, text, font, fill=(255, 255, 255), outline=(0, 0, 0), stroke=4, anchor=None):
    """
    Draw text with stroke (works on modern Pillow). Anchor supported when available.
    """
    draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)


# -------------------------
# Sprite loader
# -------------------------
def load_form_image(form_name):
    form_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png",
        "Ascended Hopper": "ascended.png",
    }
    filename = form_map.get(form_name, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


# -------------------------
# Texture / grain overlay
# -------------------------
def apply_subtle_texture(base_img, texture_path=None, intensity=0.14):
    """
    Blend a subtle paper texture. If texture_path exists, use it; otherwise generate grain.
    intensity: 0..0.4 recommended
    """
    w, h = base_img.size
    if texture_path and os.path.exists(texture_path):
        try:
            tex = Image.open(texture_path).convert("RGBA").resize((w, h))
            # desaturate texture slightly for even tone
            tex_gray = ImageOps.grayscale(tex).convert("RGBA")
            # blend warm paper color with the texture
            warm = Image.new("RGBA", (w, h), (245, 220, 185, 255))
            blended = Image.blend(warm, tex_gray, 0.25)
            blended.putalpha(int(255 * intensity))
            return Image.alpha_composite(base_img, blended)
        except Exception:
            pass

    # Procedural grain fallback
    grain = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grain)
    for y in range(0, h, 6):
        for x in range(0, w, 6):
            alpha = int(6 + random.random() * 20)
            gdraw.rectangle([x, y, x + 5, y + 5], fill=(0, 0, 0, alpha))
    grain = grain.filter(ImageFilter.GaussianBlur(1.0))
    grain.putalpha(int(255 * intensity))
    return Image.alpha_composite(base_img, grain)


# -------------------------
# Energy burst (stylized)
# -------------------------
def draw_energy_burst_on_canvas(canvas, center, max_r, color=(255, 120, 20), rings=8):
    """
    Draw layered jagged energy bursts onto canvas (RGBA). Uses temporary layers for blur/alpha.
    """
    w, h = canvas.size
    cx, cy = center
    for i in range(rings):
        t = (i + 1) / rings
        radius = int(max_r * t)
        # create jagged polygon
        points = []
        step = 16
        for a in range(0, 360, step):
            ang = math.radians(a)
            jitter = random.uniform(-0.12, 0.18) * radius
            r = radius + jitter
            x = cx + int(math.cos(ang) * r)
            y = cy + int(math.sin(ang) * r)
            points.append((x, y))
        tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        alpha = int(220 * (1 - t) * 0.9)
        td.polygon(points, fill=(color[0], color[1], color[2], alpha))
        # blur for softness
        blur_amount = max(1, int(6 * (1 - t)))
        tmp = tmp.filter(ImageFilter.GaussianBlur(blur_amount))
        canvas = Image.alpha_composite(canvas, tmp)
    return canvas


# -------------------------
# Progress bar helper
# -------------------------
def draw_progress_bar(draw, bbox, pct, fill_color=(245, 170, 30), bg_color=(220, 220, 220), outline_color=(10, 8, 6)):
    x0, y0, x1, y1 = bbox
    radius = (y1 - y0) // 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=bg_color, outline=outline_color, width=2)
    fill_w = x0 + max(4, int((x1 - x0) * max(0.0, min(1.0, pct))))
    if fill_w > x0 + 2:
        draw.rounded_rectangle([x0, y0, fill_w, y1], radius=radius, fill=fill_color)


# -------------------------
# MAIN: Profile generator (comic-cover)
# -------------------------
def generate_profile_image(user):
    """
    Comic-cover style trading-card (900x1280). Uses COVER_REF_PATH if available for texture.
    """
    user_id = user.get("user_id", "unknown")
    form = user.get("form", "Tadpole")
    level = int(user.get("level", 1))
    xp_current = int(user.get("xp_current", 0))
    xp_next = int(user.get("xp_to_next_level", 200) or 200)
    xp_total = int(user.get("xp_total", 0))
    wins = int(user.get("wins", 0))
    mobs = int(user.get("mobs_defeated", 0))
    rituals = int(user.get("rituals", 0))

    pct = max(0.0, min(1.0, xp_current / xp_next)) if xp_next > 0 else 0.0

    WIDTH, HEIGHT = 900, 1280
    base_color = (244, 216, 180, 255)  # warm paper
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), base_color)
    # Apply subtle texture (uses uploaded cover if present)
    canvas = apply_subtle_texture(canvas, texture_path=(COVER_REF_PATH if os.path.exists(COVER_REF_PATH) else None), intensity=0.14)
    draw = ImageDraw.Draw(canvas)

    # Palette
    black = (10, 8, 6)
    title_yellow = (245, 170, 30)
    energy_orange = (255, 120, 20)
    deep_purple = (45, 14, 60)
    banner_red = (170, 30, 20)
    cream = (245, 216, 180)

    # Outer frame
    pad = 20
    outer = (pad, pad, WIDTH - pad, HEIGHT - pad)
    draw.rectangle(outer, outline=black, width=12)

    # Title (MEGAGROK) - drop shadow + yellow text
    title_x = WIDTH // 2
    title_y = outer[1] + 22
    outline_text(draw, (title_x + 6, title_y + 8), "MEGAGROK", TITLE_FONT, fill=(60, 30, 10), outline=black, stroke=10, anchor="mm")
    outline_text(draw, (title_x, title_y), "MEGAGROK", TITLE_FONT, fill=title_yellow, outline=black, stroke=8, anchor="mm")
    # small subtitle
    outline_text(draw, (WIDTH - 160, outer[1] + 40), "THE COSMIC HERO", BIG_TITLE_FONT, fill=black, outline=title_yellow, stroke=3, anchor="mm")

    # Energy burst behind hero
    hero_cx = WIDTH // 2
    hero_cy = outer[1] + 420
    canvas = draw_energy_burst_on_canvas(canvas, (hero_cx, hero_cy), max_r=420, color=energy_orange, rings=10)
    draw = ImageDraw.Draw(canvas)

    # Vignette to darken edges a bit
    vign = Image.new("L", (WIDTH, HEIGHT), 0)
    vdraw = ImageDraw.Draw(vign)
    vdraw.ellipse([-WIDTH//2, -HEIGHT//2, WIDTH + WIDTH//2, HEIGHT + HEIGHT//2], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(140))
    inv = ImageOps.invert(vign)
    dark_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 70))
    canvas = Image.composite(dark_layer, canvas, inv)
    draw = ImageDraw.Draw(canvas)

    # Load and place sprite (larger for cover feel)
    sprite = load_form_image(form)
    if sprite:
        sp_w = 360
        sp = sprite.resize((sp_w, sp_w)).convert("RGBA")
        sx = hero_cx - sp.width // 2
        sy = hero_cy - sp.height // 2 + 10
        # outline the sprite with a soft black stroke for comic look
        mask = sp.split()[3]
        outline_img = Image.new("RGBA", sp.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(outline_img)
        od.bitmap((0, 0), mask, fill=(0, 0, 0))
        outline_img = outline_img.filter(ImageFilter.GaussianBlur(6))
        canvas.paste(outline_img, (sx, sy), outline_img)
        canvas.paste(sp, (sx, sy), sp)
    else:
        # fallback bold silhouette
        s = 320
        draw.ellipse([hero_cx - s//2, hero_cy - s//2, hero_cx + s//2, hero_cy + s//2], fill=(80, 80, 80))
        outline_text(draw, (hero_cx, hero_cy), "?", NUM_FONT, fill=cream, outline=black, stroke=4, anchor="mm")

    # Bottom banner (red with yellow lettering)
    banner_h = 200
    banner_y0 = outer[3] - banner_h - 8
    banner_rect = (outer[0] + 8, banner_y0, outer[2] - 8, outer[3] - 8)
    draw.rectangle(banner_rect, fill=banner_red, outline=black, width=6)
    banner_text = "THE COSMIC AMPHIBIAN AWAKENS"
    outline_text(draw, (WIDTH // 2, banner_y0 + banner_h // 2 - 6), banner_text, BIG_TITLE_FONT, fill=title_yellow, outline=black, stroke=6, anchor="mm")

    # Stats box above banner (cream box)
    stats_h = 240
    stats_w = WIDTH - 160
    stats_x0 = (WIDTH - stats_w) // 2
    stats_y0 = banner_y0 - stats_h - 28
    stats_box = (stats_x0, stats_y0, stats_x0 + stats_w, stats_y0 + stats_h)
    draw.rounded_rectangle(stats_box, radius=18, fill=cream, outline=black, width=4)

    # Inside stats layout:
    px = stats_box[0] + 24
    py = stats_box[1] + 18
    inner_w = stats_w - 48
    inner_h = stats_h - 36

    # Left column: XP big
    left_w = int(inner_w * 0.55)
    # XP heading
    deep_purple = (45, 14, 60)
    outline_text(draw, (px + 8, py), "XP", SMALL_FONT, fill=deep_purple, outline=black, stroke=2)
    outline_text(draw, (px + 8, py + 36), f"{xp_current} / {xp_next}", NUM_FONT, fill=deep_purple, outline=black, stroke=4)
    # progress bar
    bar_bbox = (px + 8, py + 120, px + 8 + left_w - 24, py + 120 + 36)
    draw_progress_bar(draw, bar_bbox, pct, fill_color=title_yellow, bg_color=(230, 230, 230), outline_color=black)
    # percentage text to the right of bar
    pct_text = f"{int(pct * 100)}%"
    outline_text(draw, (bar_bbox[2] + 28, bar_bbox[1] + 18), pct_text, HEADER_FONT, fill=deep_purple, outline=black, stroke=3, anchor="lm")

    # Right column: three stat tiles stacked
    tile_x = px + left_w + 12
    tile_w = inner_w - left_w - 12
    tile_h = int((inner_h - 12) / 3)
    def draw_tile(x, y, w, h, label, value):
        draw.rounded_rectangle([x, y, x + w - 6, y + h - 6], radius=12, fill=(250, 245, 238), outline=deep_purple, width=3)
        outline_text(draw, (x + 12, y + 8), label, SMALL_FONT, fill=deep_purple, outline=black, stroke=2)
        outline_text(draw, (x + 12, y + 40), str(value), STAT_FONT, fill=(110, 45, 150), outline=black, stroke=3)

    draw_tile(tile_x, py, tile_w, tile_h, "Lifetime XP", xp_total)
    draw_tile(tile_x, py + tile_h, tile_w, tile_h, "Wins", wins)
    draw_tile(tile_x, py + 2 * tile_h, tile_w, tile_h, "Mobs", mobs)
    # rituals small text below tiles
    outline_text(draw, (stats_box[0] + 18, stats_box[3] - 20), f"Rituals: {rituals}", SMALL_FONT, fill=deep_purple, outline=black, stroke=2)

    # footer small link right of stats
    footer = "t.me/YourMegaGrokBot"
    try:
        tb = draw.textbbox((0, 0), footer, font=SMALL_FONT)
        tw = tb[2] - tb[0]
    except Exception:
        tw = len(footer) * 8
    draw.text((stats_box[2] - tw - 12, stats_box[3] + 4), footer, font=SMALL_FONT, fill=deep_purple)

    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# -------------------------
# LEADERBOARD: Comic Cover Poster Page (Single Page Spread)
# -------------------------
# This function will layout the top 10 in a 5x2 grid in a poster-page cover style.
from bot.db import get_top_users  # local import placed here to avoid circulars in some setups

def generate_leaderboard_image():
    rows = get_top_users()
    # ensure exactly up to 10 entries
    rows = rows[:10]

    WIDTH, HEIGHT = 1400, 1800  # poster-size for social sharing
    base_color = (244, 216, 180, 255)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), base_color)
    # subtle texture from the cover reference
    canvas = apply_subtle_texture(canvas, texture_path=(COVER_REF_PATH if os.path.exists(COVER_REF_PATH) else None), intensity=0.12)
    draw = ImageDraw.Draw(canvas)

    # Palette
    black = (10, 8, 6)
    title_yellow = (245, 170, 30)
    purple_deep = (45, 14, 60)
    red_banner = (170, 30, 20)
    cream = (245, 216, 180)
    energy_orange = (255, 120, 20)

    # Outer border
    pad = 28
    outer = (pad, pad, WIDTH - pad, HEIGHT - pad)
    draw.rectangle(outer, outline=black, width=16)

    # Header
    outline_text(draw, (WIDTH // 2, outer[1] + 48), "MEGAGROK — TOP HEROES ISSUE", BIG_TITLE_FONT, fill=title_yellow, outline=black, stroke=8, anchor="mm")
    outline_text(draw, (WIDTH // 2, outer[1] + 118), "TOP 10 TAMERS", HEADER_FONT, fill=purple_deep, outline=black, stroke=4, anchor="mm")

    # Decorative energy background behind grid (light)
    center_x = WIDTH // 2
    center_y = outer[1] + 420
    canvas = draw_energy_burst_on_canvas(canvas, (center_x, center_y), max_r=520, color=energy_orange, rings=8)
    draw = ImageDraw.Draw(canvas)

    # Grid: 5 rows x 2 columns
    cols = 2
    rows_count = 5
    grid_margin_x = 80
    grid_margin_y = 220
    grid_w = WIDTH - grid_margin_x * 2
    grid_h = HEIGHT - grid_margin_y * 2 - 260  # leave space for header/footer
    cell_w = grid_w // cols
    cell_h = grid_h // rows_count

    start_x = grid_margin_x
    start_y = grid_margin_y + 120

    for idx in range(10):
        col = idx % cols
        row_idx = idx // cols
        x0 = start_x + col * cell_w + 18
        y0 = start_y + row_idx * cell_h + 12
        x1 = x0 + cell_w - 36
        y1 = y0 + cell_h - 24

        # Background panel for each hero (white-ish with purple outline)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=cream, outline=purple_deep, width=5)

        # Rank number top-left
        rank = idx + 1
        outline_text(draw, (x0 + 28, y0 + 22), f"#{rank}", NUM_FONT, fill=purple_deep, outline=black, stroke=4, anchor="lm")

        # If we have user data
        if idx < len(rows):
            u = rows[idx]
            uid = u.get("user_id", "?")
            lvl = u.get("level", 1)
            xp_total = u.get("xp_total", u.get("xp", 0))
            form = u.get("form", "Tadpole")

            # sprite
            sprite = load_form_image(form)
            if sprite:
                sp = sprite.resize((120, 120)).convert("RGBA")
                sp_x = x0 + 140
                sp_y = y0 + 20
                canvas.paste(sp, (sp_x, sp_y), sp)
            else:
                outline_text(draw, (x0 + 160, y0 + 80), "??", NUM_FONT, fill=black, outline=purple_deep, stroke=3, anchor="mm")

            # Name and stats
            outline_text(draw, (x0 + 300, y0 + 34), f"User {uid}", HEADER_FONT, fill=purple_deep, outline=black, stroke=3, anchor="lm")
            draw.text((x0 + 300, y0 + 86), f"Lvl {lvl} — {xp_total} XP", font=BODY_FONT, fill=(50, 20, 60))

            # small progress mini-bar (if xp_to_next present)
            xp_c = int(u.get("xp_current", 0))
            xp_n = int(u.get("xp_to_next_level", 200) or 200)
            pct = xp_c / xp_n if xp_n > 0 else 0.0
            mini_bar_bbox = (x0 + 300, y0 + 118, x0 + 620, y0 + 142)
            draw_progress_bar(draw, mini_bar_bbox, pct, fill_color=title_yellow, bg_color=(230, 230, 230), outline_color=black)

        else:
            # empty slot
            outline_text(draw, (x0 + 160, y0 + 60), "EMPTY", HEADER_FONT, fill=(120, 120, 120), outline=black, stroke=3, anchor="mm")

    # Footer
    footer_text = "MEGAGROK — HOP-FAME"
    outline_text(draw, (WIDTH // 2, outer[3] - 56), footer_text, BIG_TITLE_FONT, fill=title_yellow, outline=black, stroke=6, anchor="mm")

    out = "/tmp/leaderboard.png"
    canvas.save(out)
    return out
