# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING (safe fallback)
# ---------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = load_font(60)
HEADER_FONT = load_font(40)
STAT_FONT = load_font(34)
SMALL_FONT = load_font(20)
BODY_FONT = load_font(24)

# ---------------------------------------------------
# OUTLINE TEXT HELPER (stroke-safe)
# ---------------------------------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    """
    Draw text with stroke. Uses stroke parameters when available.
    """
    # Pillow supports stroke_width/stroke_fill; this will work on modern Pillow
    draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)


# ---------------------------------------------------
# SPRITE LOADER
# ---------------------------------------------------
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


# ---------------------------------------------------
# UTILS: text center helper (safe textbbox)
# ---------------------------------------------------
def text_size(draw, text, font):
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        return (bbox[2]-bbox[0], bbox[3]-bbox[1])
    except Exception:
        # fallback approximate
        return font.getsize(text) if hasattr(font, "getsize") else (len(text)*8, 16)


# ---------------------------------------------------
# TRADING CARD — COSMIC PURPLE THEME
# ---------------------------------------------------
def generate_profile_image(user):
    """
    Trading-card style profile (cosmic purple + silver highlights).
    Shows: User, Level, Grok sprite (reduced), XP bar, Lifetime XP, Wins, Mobs, Rituals.
    """
    # --- read user fields with safe fallbacks ---
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

    # --- canvas ---
    WIDTH, HEIGHT = 900, 1280
    paper = (26, 12, 40)            # deep purple background
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), paper + (255,))
    draw = ImageDraw.Draw(canvas)

    # --- palette (cosmic purple + silver)
    purple_dark = (40, 10, 80)
    purple_mid = (110, 45, 150)
    silver = (210, 210, 220)
    cream = (245, 240, 230)
    accent = (170, 130, 255)

    # --- comic border (black outer + purple mid inset + silver inner)
    M = 28
    outer = (M, M, WIDTH - M, HEIGHT - M)
    draw.rectangle(outer, outline=(0,0,0), width=10)

    inset = 12
    mid_rect = (outer[0]+inset, outer[1]+inset, outer[2]-inset, outer[3]-inset)
    draw.rectangle(mid_rect, outline=purple_mid, width=8)

    inner = (mid_rect[0]+8, mid_rect[1]+8, mid_rect[2]-8, mid_rect[3]-8)
    draw.rectangle(inner, outline=silver, width=4)

    # --- header ribbon ---
    header_y = inner[1] + 40
    outline_text(draw, (WIDTH//2, header_y), "MEGAGROK TRADING CARD", TITLE_FONT,
                 fill=accent, outline=purple_dark, stroke=6, anchor="mm")

    # --- user & level lines ---
    outline_text(draw, (WIDTH//2, header_y + 70), f"User {user_id}", HEADER_FONT,
                 fill=silver, outline=purple_dark, stroke=4, anchor="mm")
    outline_text(draw, (WIDTH//2, header_y + 120), f"Level {level}", HEADER_FONT,
                 fill=silver, outline=purple_dark, stroke=4, anchor="mm")

    # --- grok sprite (reduced 50% -> 260x260) ---
    sprite = load_form_image(form)
    sprite_y = inner[1] + 210
    if sprite:
        sp = sprite.resize((260, 260)).convert("RGBA")
        sx = WIDTH//2 - sp.width//2
        canvas.paste(sp, (sx, sprite_y), sp)
    else:
        # fallback
        draw.ellipse([WIDTH//2 - 130, sprite_y, WIDTH//2 + 130, sprite_y + 260], fill=(90,90,90))
        outline_text(draw, (WIDTH//2, sprite_y + 130), "??", HEADER_FONT, fill=silver, outline=purple_dark, stroke=3, anchor="mm")

    # --- stats panel (bottom) ---
    stats_h = 360
    stats_rect = (
        inner[0] + 36,
        inner[3] - stats_h - 36,
        inner[2] - 36,
        inner[3] - 36
    )
    draw.rounded_rectangle(stats_rect, radius=22, fill=cream, outline=purple_dark, width=5)

    sx = stats_rect[0] + 36
    sy = stats_rect[1] + 28

    # XP heading
    outline_text(draw, (sx, sy), "XP PROGRESS", STAT_FONT, fill=purple_dark, outline=silver, stroke=3)

    # XP progress bar
    bar_x0 = sx
    bar_y0 = sy + 56
    bar_x1 = stats_rect[2] - 36
    bar_y1 = bar_y0 + 42
    # background bar
    draw.rounded_rectangle([bar_x0, bar_y0, bar_x1, bar_y1], radius=21, fill=(220,220,220))
    # fill
    fill_w = int((bar_x1 - bar_x0) * pct)
    if fill_w > 0:
        draw.rounded_rectangle([bar_x0, bar_y0, bar_x0 + fill_w, bar_y1], radius=21, fill=purple_mid)
    # XP numeric to the right
    xp_text = f"{xp_current}/{xp_next} ({int(pct*100)}%)"
    try:
        tb = draw.textbbox((0,0), xp_text, font=BODY_FONT)
        tw = tb[2] - tb[0]
    except Exception:
        tw = text_size(draw, xp_text, BODY_FONT)[0]
    draw.text((bar_x1 - tw, bar_y0 - 36), xp_text, font=BODY_FONT, fill=purple_dark)

    # move pointer down for the rest stats
    sy = bar_y1 + 36

    # Visual stat tiles: Lifetime XP, Wins, Mobs, Rituals
    tile_w = (stats_rect[2] - stats_rect[0] - 2*36) // 4
    tile_h = 120
    tx = stats_rect[0] + 36
    ty = sy

    def draw_stat_tile(x, y, w, h, label, value, color_bg=(250,250,250)):
        # tile BG
        draw.rounded_rectangle([x, y, x + w - 8, y + h], radius=12, fill=color_bg, outline=purple_dark, width=2)
        # label
        outline_text(draw, (x + 16, y + 10), label, SMALL_FONT, fill=purple_dark, outline=silver, stroke=2)
        # value (big)
        outline_text(draw, (x + 16, y + 44), str(value), STAT_FONT, fill=purple_mid, outline=purple_dark, stroke=3)

    # Lifetime XP
    draw_stat_tile(tx, ty, tile_w, tile_h, "Lifetime XP", xp_total, color_bg=(250,247,245))
    tx += tile_w
    draw_stat_tile(tx, ty, tile_w, tile_h, "Wins", wins, color_bg=(250,247,245))
    tx += tile_w
    draw_stat_tile(tx, ty, tile_w, tile_h, "Mobs", mobs, color_bg=(250,247,245))
    tx += tile_w
    draw_stat_tile(tx, ty, tile_w, tile_h, "Rituals", rituals, color_bg=(250,247,245))

    # --- small footer (bot link) ---
    footer = "t.me/YourMegaGrokBot"
    try:
        tb = draw.textbbox((0,0), footer, font=SMALL_FONT)
        tw = tb[2] - tb[0]
    except Exception:
        tw = text_size(draw, footer, SMALL_FONT)[0]
    draw.text((inner[2] - 28 - tw, inner[3] - 28), footer, font=SMALL_FONT, fill=purple_mid)

    # --- export ---
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# ---------------------------------------------------
# LEADERBOARD (simple, purple-themed)
# ---------------------------------------------------
def generate_leaderboard_image():
    rows = get_top_users()
    WIDTH = 900
    ROW_H = 120
    HEIGHT = 160 + len(rows) * ROW_H

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (26,12,40,255))
    draw = ImageDraw.Draw(canvas)

    outline_text(draw, (WIDTH//2, 56), "MEGAGROK HOP-FAME", TITLE_FONT, fill=(210,190,255), outline=(40,10,80), stroke=6, anchor="mm")

    y = 120
    for i, user in enumerate(rows, start=1):
        # row bg
        draw.rectangle([(40, y), (WIDTH-40, y + ROW_H - 20)], fill=(250,250,250), outline=(40,10,80), width=3)
        outline_text(draw, (70, y + 36), f"#{i}", HEADER_FONT, fill=(40,10,80), outline=(210,210,220), stroke=4)
        sprite = load_form_image(user.get("form", "Tadpole"))
        if sprite:
            sp = sprite.resize((96,96))
            canvas.paste(sp, (170, y + 12), sp)
        outline_text(draw, (300, y + 20), f"User {user.get('user_id','?')}", BODY_FONT, fill=(40,10,80), outline=(210,210,220), stroke=3)
        draw.text((300, y + 62), f"Lvl {user.get('level',1)} — {user.get('xp_total', 0)} XP", font=SMALL_FONT, fill=(60,60,80))
        y += ROW_H

    out = "/tmp/leaderboard.png"
    canvas.save(out)
    return out
