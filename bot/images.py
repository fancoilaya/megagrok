# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING
# ---------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT   = load_font(56)
BODY_FONT    = load_font(28)
SMALL_FONT   = load_font(20)
STAT_FONT    = load_font(34)
HERO_FONT    = load_font(40)


# ---------------------------------------------------
# OUTLINE TEXT (stroke-safe)
# ---------------------------------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=4):
    """
    Draw text with stroke parameters (works on modern Pillow).
    """
    draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline)


# ---------------------------------------------------
# LOAD GROK SPRITE
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
# HALFTONE COMIC TEXTURE (background only)
# ---------------------------------------------------
def apply_halftone(img):
    """
    Very subtle halftone/dot overlay to give a comic-paper texture.
    Only adds a faint dot grid on top of `img`.
    """
    overlay = Image.new("RGBA", img.size, (255,255,255,0))
    dot = Image.new("RGBA", (8,8), (0,0,0,35))
    for y in range(0, img.size[1], 8):
        for x in range(0, img.size[0], 8):
            if (x//8 + y//8) % 2 == 0:
                overlay.paste(dot, (x, y), dot)
    return Image.alpha_composite(img, overlay)


# ---------------------------------------------------
# MAIN PROFILE TRADING CARD
# ---------------------------------------------------
def generate_profile_image(user):
    """
    Produces a vertical trading-card style profile image (900x1280).
    Expects 'user' dict with keys:
      user_id, form, level, xp_current, xp_to_next_level, xp_total, wins, mobs_defeated, rituals
    """

    # --- Extract user fields (safe defaults) ---
    user_id    = user.get("user_id", "unknown")
    form       = user.get("form", "Tadpole")
    level      = int(user.get("level", 1))
    xp_current = int(user.get("xp_current", 0))
    xp_next    = int(user.get("xp_to_next_level", 200) or 200)
    xp_total   = int(user.get("xp_total", 0))
    wins       = int(user.get("wins", 0))
    mobs       = int(user.get("mobs_defeated", 0))
    rituals    = int(user.get("rituals", 0))

    pct = 0.0
    if xp_next > 0:
        pct = max(0.0, min(1.0, xp_current / xp_next))

    # --- Canvas / Background ---
    width, height = 900, 1280

    neb_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(neb_path):
        # COPY nebula exactly (no blending/tint) to avoid color fog
        canvas = Image.open(neb_path).convert("RGBA").resize((width, height)).copy()
    else:
        # matte paper fallback (light cream)
        canvas = Image.new("RGBA", (width, height), (255, 249, 230, 255))

    # apply subtle halftone texture to the background only
    canvas = apply_halftone(canvas)

    draw = ImageDraw.Draw(canvas)

    # ---------------------------------------------------
    # COMIC BORDER (yellow + black heavy outline)
    # ---------------------------------------------------
    margin = 26
    outer = (margin, margin, width - margin, height - margin)

    # heavy black outer border
    draw.rectangle(outer, outline=(0,0,0), width=10)

    # yellow plated inset
    inset = 14
    yellow_rect = (
        outer[0] + inset,
        outer[1] + inset,
        outer[2] - inset,
        outer[3] - inset
    )
    draw.rectangle(yellow_rect, outline=(255,215,80), width=8)

    # inner comic white/ink border
    inner = (
        yellow_rect[0] + 10,
        yellow_rect[1] + 10,
        yellow_rect[2] - 10,
        yellow_rect[3] - 10
    )
    draw.rectangle(inner, outline=(30,30,30), width=4)

    # ---------------------------------------------------
    # TITLE
    # ---------------------------------------------------
    title_pos = (inner[0] + 30, inner[1] + 20)
    outline_text(draw, title_pos, "MEGAGROK: HERO PROFILE", TITLE_FONT,
                 fill=(250,240,200), outline=(40,10,80), stroke=6)

    # ---------------------------------------------------
    # HERO (centered, large)
    # ---------------------------------------------------
    sprite = load_form_image(form)
    hero_cx = width // 2
    hero_cy = inner[1] + 380

    if sprite:
        # halo behind sprite (matte, soft)
        halo = sprite.copy().resize((int(sprite.width * 2.4), int(sprite.height * 2.4)))
        halo = halo.filter(ImageFilter.GaussianBlur(42))
        tint = Image.new("RGBA", halo.size, (255,180,60,80))
        halo = Image.alpha_composite(halo, tint)
        hx = hero_cx - halo.width // 2
        hy = hero_cy - halo.height // 2
        canvas.paste(halo, (hx, hy), halo)

        # main sprite (no xp ring)
        sp = sprite.resize((420, 420)).convert("RGBA")
        sx = hero_cx - sp.width // 2
        sy = hero_cy - sp.height // 2
        canvas.paste(sp, (sx, sy), sp)
    else:
        # fallback silhouette
        draw.ellipse([hero_cx - 200, hero_cy - 200, hero_cx + 200, hero_cy + 200], fill=(70,70,70))
        outline_text(draw, (hero_cx - 18, hero_cy - 18), "??", HERO_FONT, fill=(255,255,255), outline=(0,0,0), stroke=3)

    # ---------------------------------------------------
    # BOTTOM STATS BAR (centered hero -> bottom bar)
    # ---------------------------------------------------
    bar_h = 240
    bar_top = inner[3] - bar_h

    bar_rect = (
        inner[0] + 30,
        bar_top,
        inner[2] - 30,
        inner[3] - 30
    )
    draw.rounded_rectangle(bar_rect, radius=20, fill=(255,245,205), outline=(0,0,0), width=5)

    # Stats content positions
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

    # ---------------------------------------------------
    # BADGES ROW (inside bottom bar)
    # ---------------------------------------------------
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

    # ---------------------------------------------------
    # FOOTER LINK
    # ---------------------------------------------------
    footer = "t.me/YourMegaGrokBot"
    try:
        tbbox = draw.textbbox((0,0), footer, font=SMALL_FONT)
        tw = tbbox[2] - tbbox[0]
    except Exception:
        tw = 0
    draw.text((inner[2] - 20 - tw, inner[3] - 40), footer, font=SMALL_FONT, fill=(50,50,50))

    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# ---------------------------------------------------
# LEADERBOARD (retained; minor safe adjustments)
# ---------------------------------------------------
def generate_leaderboard_image():
    rows = get_top_users()

    width = 1000
    height = 200 + len(rows) * 140
    img = Image.new("RGBA", (width, height), (22, 18, 40, 255))

    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        neb = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, neb)

    draw = ImageDraw.Draw(img)

    outline_text(draw, (width // 2 - 260, 40), "MEGAGROK HOP-FAME", load_font(56), fill=(255,230,120),
                 outline=(40,0,80), stroke=6)

    y = 160
    for i, user in enumerate(rows):
        rank = i + 1

        draw.rectangle([(40, y), (width - 40, y + 110)], outline=(255,255,255,60), width=2)

        outline_text(draw, (60, y + 30), f"#{rank}", HERO_FONT, fill=(255,255,180), outline=(0,0,0), stroke=4)

        sprite = load_form_image(user.get("form", "Tadpole"))
        if sprite:
            sp = sprite.resize((110, 110))
            img.paste(sp, (180, y), sp)

        outline_text(draw, (350, y + 20), f"User {user['user_id']}", BODY_FONT, fill=(255,255,255),
                     outline=(0,0,0), stroke=3)

        try:
            xp_total = user.get("xp_total", 0)
        except Exception:
            xp_total = 0

        draw.text((350, y + 70), f"Lvl {user.get('level', 1)} — {xp_total} XP", font=SMALL_FONT, fill=(255,255,255))

        y += 140

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
