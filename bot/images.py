# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont

ASSETS = "assets"

# Base templates
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"

# Sprites
TADPOLE = "tadpole.png"
HOPPER = "hopper.png"
ASCENDED = "ascended.png"

# Fonts
FONTS = {
    "bold": "Roboto-Bold.ttf",
    "regular": "Roboto-Regular.ttf",
    "light": "Roboto-Light.ttf"
}

# -----------------------------
# FONT LOADING
# -----------------------------
def _font(name, size):
    paths = [
        os.path.join(ASSETS, name),
        os.path.join("/mnt/data", name),
        name
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

FONT_TITLE = _font(FONTS["bold"], 72)
FONT_USERNAME = _font(FONTS["bold"], 48)
FONT_LABEL = _font(FONTS["regular"], 40)
FONT_VALUE = _font(FONTS["bold"], 56)
FONT_FOOTER = _font(FONTS["light"], 32)
FONT_ROW_NAME = _font(FONTS["bold"], 40)
FONT_ROW_STATS = _font(FONTS["regular"], 34)

# -----------------------------
# IMAGE LOADING
# -----------------------------
def _load_img(name):
    for p in (
        os.path.join(ASSETS, name),
        os.path.join("/mnt/data", name),
        name
    ):
        if os.path.exists(p):
            return Image.open(p).convert("RGBA")
    return None

FORM_SPRITES = {
    "Tadpole": TADPOLE,
    "Hopper": HOPPER,
    "Ascended": ASCENDED
}

# ================================================================
#                     PROFILE GENERATOR
# ================================================================
def generate_profile_image(user):
    username = user.get("username", "Unknown")
    level = int(user.get("level", 1))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    form = user.get("form", "Tadpole")
    tg = user.get("tg", "")
    ca = user.get("ca", "")

    base = _load_img(PROFILE_BASE)
    if base is None:
        return None

    W, H = base.size
    draw = ImageDraw.Draw(base)

    # --------------------
    # HEADER
    # --------------------
    title = "MEGAGROK"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((W - tw) / 2, 35), title, font=FONT_TITLE, fill=(0, 0, 0))

    uw = draw.textlength(username, font=FONT_USERNAME)
    draw.text(((W - uw) / 2, 120), username, font=FONT_USERNAME, fill=(0, 0, 0))

    # --------------------
    # STATS (LEFT COLUMN)
    # --------------------
    X = 70
    Y = 240

    draw.text((X, Y), "LEVEL", font=FONT_LABEL, fill=(0, 0, 0))
    draw.text((X, Y + 45), str(level), font=FONT_VALUE, fill=(0, 0, 0))

    draw.text((X, Y + 140), "FIGHTS / WINS", font=FONT_LABEL, fill=(0, 0, 0))
    draw.text((X, Y + 185), f"{fights} / {wins}", font=FONT_VALUE, fill=(0, 0, 0))

    draw.text((X, Y + 280), "RITUALS", font=FONT_LABEL, fill=(0, 0, 0))
    draw.text((X, Y + 325), str(rituals), font=FONT_VALUE, fill=(0, 0, 0))

    # --------------------
    # SPRITE
    # --------------------
    sprite = _load_img(FORM_SPRITES.get(form, TADPOLE))
    if sprite:
        sp_w = 420
        aspect = sprite.height / sprite.width
        sp_h = int(sp_w * aspect)
        sprite = sprite.resize((sp_w, sp_h), Image.LANCZOS)

        sx = 1024 - sp_w - 80
        sy = 350
        base.paste(sprite, (sx, sy), sprite)

    # --------------------
    # FOOTER
    # --------------------
    footer_y = 1240

    if tg:
        draw.text((70, footer_y), f"TG: {tg}", font=FONT_FOOTER, fill=(0, 0, 0))
    if ca:
        draw.text((70, footer_y + 40), f"CA: {ca}", font=FONT_FOOTER, fill=(0, 0, 0))

    # Output
    out = f"/tmp/profile_{user.get('user_id', 'x')}.png"
    base.save(out)
    return out


# ================================================================
#                    LEADERBOARD GENERATOR
# ================================================================
def generate_leaderboard_image():
    try:
        from bot.db import get_top_users
        rows = get_top_users(5)
    except:
        rows = []

    base = _load_img(LEADERBOARD_BASE)
    if base is None:
        return None

    W, H = base.size
    draw = ImageDraw.Draw(base)

    # --------------------
    # HEADER
    # --------------------
    title = "TOP 5 LEADERBOARD"
    tw = draw.textlength(title, font=FONT_TITLE)
    draw.text(((W - tw) / 2, 45), title, font=FONT_TITLE, fill=(0, 0, 0))

    # --------------------
    # ROW COORDINATES
    # --------------------
    ROW_TOP_START = 230
    ROW_HEIGHT = 210

    for i, r in enumerate(rows):
        y = ROW_TOP_START + i * ROW_HEIGHT

        # Rank number (large number inside circle)
        rank = str(i + 1)
        draw.text((100, y + 50), rank, font=FONT_VALUE, fill=(0, 0, 0))

        # Sprite
        sprite = _load_img(FORM_SPRITES.get(r.get("form", "Tadpole"), TADPOLE))
        if sprite:
            sp = sprite.resize((160, 160), Image.LANCZOS)
            base.paste(sp, (200, y + 10), sp)

        # Username
        name = r.get("username", f"User{r['user_id']}")
        draw.text((390, y + 35), name, font=FONT_ROW_NAME, fill=(0, 0, 0))

        # Stats line:
        xp = r.get("xp_total", 0)
        fights = r.get("mobs_defeated", r.get("fights", 0))
        wins = r.get("wins", 0)

        stat = f"XP: {xp}     FIGHTS / WINS: {fights} / {wins}"
        draw.text((390, y + 95), stat, font=FONT_ROW_STATS, fill=(0, 0, 0))

    # Output
    out = "/tmp/leaderboard.png"
    base.save(out)
    return out
