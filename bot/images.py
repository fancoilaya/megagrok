# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from bot.db import get_top_users

ASSET_DIR = "assets"

# -------------------------
# Font loader (safe fallback)
# -------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = load_font(46)
HERO_FONT  = load_font(36)
STAT_FONT  = load_font(32)
BODY_FONT  = load_font(22)
SMALL_FONT = load_font(16)


# -------------------------
# Outline text helper
# -------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    """
    Draw text with stroke. Uses pillow stroke_width/stroke_fill.
    """
    draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)


# -------------------------
# Load Grok sprite
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
# Subtle halftone (background only)
# -------------------------
def apply_halftone_background(img, dot_size=8, alpha=28):
    """
    Apply a subtle dot grid over the background to simulate comic paper.
    This returns a composited image; it does not alter foreground elements.
    """
    overlay = Image.new("RGBA", img.size, (255,255,255,0))
    dot = Image.new("RGBA", (dot_size, dot_size), (0,0,0,alpha))
    ox, oy = 0, 0
    for y in range(0, img.size[1], dot_size):
        for x in range(0, img.size[0], dot_size):
            # offset pattern to avoid perfect grid moiré
            if ((x//dot_size) + (y//dot_size)) % 2 == 0:
                overlay.paste(dot, (x, y), dot)
    return Image.alpha_composite(img, overlay)


# -------------------------
# Main profile card generator
# -------------------------
def generate_profile_image(user):
    """
    Generates a vertical comic trading-card profile (900x1280).
    Expected user keys (safe defaults used):
      user_id, form, level, xp_current, xp_to_next_level, xp_total,
      wins, mobs_defeated, rituals
    """
    # --- read user fields with fallbacks ---
    user_id = user.get("user_id", "unknown")
    form = user.get("form", "Tadpole")
    level = int(user.get("level", 1))
    xp_current = int(user.get("xp_current", 0))
    xp_next = int(user.get("xp_to_next_level", 200) or 200)
    xp_total = int(user.get("xp_total", 0))
    wins = int(user.get("wins", 0))
    mobs = int(user.get("mobs_defeated", 0))
    rituals = int(user.get("rituals", 0))

    pct = 0.0
    if xp_next > 0:
        pct = max(0.0, min(1.0, xp_current / xp_next))

    # --- canvas setup (clean matte paper) ---
    WIDTH, HEIGHT = 900, 1280
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (255, 249, 230, 255))  # warm off-white paper

    # subtle halftone texture applied to background only
    canvas = apply_halftone_background(canvas, dot_size=8, alpha=22)

    draw = ImageDraw.Draw(canvas)

    # -------------------------
    # Classic comic border (black outer, yellow inset, inner ink line)
    # -------------------------
    M = 26  # margin
    outer = (M, M, WIDTH - M, HEIGHT - M)

    # heavy black outer border
    draw.rectangle(outer, outline=(0,0,0), width=10)

    # yellow inset plate
    INSET = 14
    yellow_rect = (outer[0] + INSET, outer[1] + INSET, outer[2] - INSET, outer[3] - INSET)
    draw.rectangle(yellow_rect, outline=(255,215,80), width=8)

    # white/ink inner border
    inner = (yellow_rect[0] + 10, yellow_rect[1] + 10, yellow_rect[2] - 10, yellow_rect[3] - 10)
    draw.rectangle(inner, outline=(30,30,30), width=4)

    # -------------------------
    # Title
    # -------------------------
    title_pos = (inner[0] + 30, inner[1] + 18)
    outline_text(draw, title_pos, "MEGAGROK: HERO PROFILE", TITLE_FONT,
                 fill=(255,245,200), outline=(40,10,80), stroke=6)

    # -------------------------
    # Centered Hero
    # -------------------------
    sprite = load_form_image(form)
    hero_cx = WIDTH // 2
    hero_cy = inner[1] + 380  # vertical placement tuned visually

    if sprite:
        # halo behind sprite: soft, matte (no strong tint)
        halo_size = (int(sprite.width * 2.4), int(sprite.height * 2.4))
        halo = sprite.copy().resize(halo_size).filter(ImageFilter.GaussianBlur(42))
        # gentle warm tint to halo, low opacity
        tint = Image.new("RGBA", halo.size, (255, 180, 60, 70))
        halo = Image.alpha_composite(halo, tint)
        hx = hero_cx - halo.width // 2
        hy = hero_cy - halo.height // 2
        canvas.paste(halo, (hx, hy), halo)

        # main sprite (large, centered)
        sp = sprite.resize((420, 420)).convert("RGBA")
        sx = hero_cx - sp.width // 2
        sy = hero_cy - sp.height // 2
        canvas.paste(sp, (sx, sy), sp)
    else:
        # fallback silhouette
        draw.ellipse([hero_cx-200, hero_cy-200, hero_cx+200, hero_cy+200], fill=(70,70,70))
        outline_text(draw, (hero_cx - 18, hero_cy - 18), "??", HERO_FONT, fill=(255,255,255), outline=(0,0,0), stroke=3)

    # -------------------------
    # Bottom stats bar (horizontal)
    # -------------------------
    bar_h = 240
    bar_top = inner[3] - bar_h
    bar_rect = (inner[0] + 30, bar_top, inner[2] - 30, inner[3] - 30)

    draw.rounded_rectangle(bar_rect, radius=20, fill=(255,245,205), outline=(0,0,0), width=5)

    # Stats text positions
    left_x = bar_rect[0] + 36
    top_y = bar_rect[1] + 26

    # LEVEL (prominent)
    outline_text(draw, (left_x, top_y), f"LEVEL {level}", HERO_FONT,
                 fill=(20,20,20), outline=(255,200,40), stroke=4)

    # XP numeric
    xp_y = top_y + 70
    outline_text(draw, (left_x, xp_y),
                 f"XP {xp_current}/{xp_next}  ({int(pct*100)}%)",
                 BODY_FONT, fill=(40,40,40), outline=(255,200,40), stroke=2)

    # wins / mobs / rituals row
    row_y = xp_y + 60
    outline_text(draw, (left_x, row_y), f"WINS: {wins}", BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (left_x + 260, row_y), f"MOBS: {mobs}", BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (left_x + 500, row_y), f"RITUALS: {rituals}", BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)

    # -------------------------
    # Badges row (inside bottom bar)
    # -------------------------
    badges_dir = os.path.join(ASSET_DIR, "badges")
    if os.path.isdir(badges_dir):
        bx = bar_rect[0] + 36
        by = bar_rect[3] - 100
        for fname in sorted(os.listdir(badges_dir))[:6]:
            path = os.path.join(badges_dir, fname)
            try:
                badge = Image.open(path).convert("RGBA").resize((72,72))
                canvas.paste(badge, (bx, by), badge)
                bx += 86
            except Exception:
                continue

    # -------------------------
    # Footer small link
    # -------------------------
    footer = "t.me/YourMegaGrokBot"
    try:
        tb = draw.textbbox((0,0), footer, font=SMALL_FONT)
        tw = tb[2] - tb[0]
    except Exception:
        tw = 0
    draw.text((inner[2] - 20 - tw, inner[3] - 40), footer, font=SMALL_FONT, fill=(60,60,60))

    # -------------------------
    # Save and return
    # -------------------------
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# -------------------------
# Leaderboard image (keeps style, safe)
# -------------------------
def generate_leaderboard_image():
    rows = get_top_users()

    width = 1000
    height = 200 + len(rows) * 140
    img = Image.new("RGBA", (width, height), (22,18,40,255))

    draw = ImageDraw.Draw(img)

    outline_text(draw, (width//2 - 260, 40), "MEGAGROK HOP-FAME", TITLE_FONT,
                 fill=(255,230,120), outline=(80,20,100), stroke=6)

    y = 160
    for i, user in enumerate(rows):
        rank = i + 1
        # row background
        draw.rectangle([(40, y), (width - 40, y + 110)], outline=(255,255,255,60), width=2)

        outline_text(draw, (60, y + 30), f"#{rank}", HERO_FONT, fill=(255,255,180), outline=(0,0,0), stroke=4)

        sprite = load_form_image(user.get("form", "Tadpole"))
        if sprite:
            sp = sprite.resize((110, 110))
            img.paste(sp, (180, y), sp)

        outline_text(draw, (350, y + 20), f"User {user['user_id']}", BODY_FONT, fill=(255,255,255), outline=(0,0,0), stroke=3)

        xp_total = user.get("xp_total", 0) if isinstance(user, dict) else 0
        draw.text((350, y + 70), f"Lvl {user.get('level', 1)} — {xp_total} XP", font=SMALL_FONT, fill=(255,255,255))

        y += 140

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
