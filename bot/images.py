# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

# -------------------------
# DEFAULT FONT (safe)
# -------------------------
def font(size: int):
    """Returns Pillow default font scaled safely (no missing font errors)."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "fonts", "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

# -------------------------
# EVOLUTION SPRITES
# -------------------------
def load_sprite(form):
    form = form.lower()
    if form == "tadpole":
        path = os.path.join(ASSET_DIR, "tadpole.png")
    elif form == "hopper":
        path = os.path.join(ASSET_DIR, "hopper.png")
    elif form == "ascended":
        path = os.path.join(ASSET_DIR, "ascended.png")
    else:
        path = os.path.join(ASSET_DIR, "tadpole.png")

    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")

# ======================================================
# PROFILE CARD GENERATOR (uses profile_base.png)
# ======================================================
def generate_profile_image(user):
    """
    Draws overlay text & sprite ON TOP of profile_base.png.
    """

    username = user.get("username", f"User {user['user_id']}")
    level = user.get("level", 1)
    wins = user.get("wins", 0)
    fights = user.get("mobs_defeated", 0)
    rituals = user.get("rituals", 0)
    form = user.get("form", "Tadpole")

    # Paths
    base_path = os.path.join(ASSET_DIR, "profile_base.png")
    if not os.path.exists(base_path):
        raise FileNotFoundError("profile_base.png missing from assets!")

    base = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # -------------------------
    # FONT SIZES
    # -------------------------
    TITLE = font(64)
    USER_FONT = font(48)
    STAT_FONT = font(42)
    SMALL = font(34)

    # -------------------------
    # TEXT: MegaGrok (centered top)
    # -------------------------
    w, h = base.size
    title_text = "MEGAGROK"
    tw, th = draw.textsize(title_text, TITLE)
    draw.text(((w - tw) // 2, 80), title_text, fill="black", font=TITLE)

    # -------------------------
    # Username centered below title
    # -------------------------
    uw, uh = draw.textsize(username, USER_FONT)
    draw.text(((w - uw) // 2, 180), username, fill="black", font=USER_FONT)

    # -------------------------
    # LEFT COLUMN (Level, Wins, Rituals)
    # -------------------------
    x = 80
    y = 350

    # LEVEL
    draw.text((x, y), "LEVEL", fill="black", font=STAT_FONT)
    draw.text((x, y + 55), str(level), fill="black", font=STAT_FONT)

    # WINS / FIGHTS
    draw.text((x, y + 160), "FIGHTS / WINS", fill="black", font=STAT_FONT)
    draw.text((x, y + 215), f"{fights} / {wins}", fill="black", font=STAT_FONT)

    # RITUALS
    draw.text((x, y + 330), "RITUALS", fill="black", font=STAT_FONT)
    draw.text((x, y + 385), str(rituals), fill="black", font=STAT_FONT)

    # -------------------------
    # TG + CA FOOTER
    # -------------------------
    tg_text = "TG: t.me/megagrok"
    ca_text = "CA: FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

    draw.text((80, h - 180), tg_text, fill="black", font=SMALL)
    draw.text((80, h - 130), ca_text, fill="black", font=SMALL)

    # -------------------------
    # SPRITE (evolution PNG placed inside right frame)
    # -------------------------
    sprite = load_sprite(form)
    if sprite:
        sprite = sprite.resize((520, 520))  # perfect fit inside template
        base.paste(sprite, (w - 620, 360), sprite)

    out = f"/tmp/profile_{user['user_id']}.png"
    base.save(out)
    return out

# ======================================================
# LEADERBOARD GENERATOR (uses leaderboard_base.png)
# ======================================================
def generate_leaderboard_image(users=None):
    """
    Accepts list of dict users = get_top_users()
    Draws 5 rows of overlay text.
    """

    if users is None:
        from bot.db import get_top_users
        users = get_top_users(5)

    base_path = os.path.join(ASSET_DIR, "leaderboard_base.png")
    if not os.path.exists(base_path):
        raise FileNotFoundError("leaderboard_base.png missing!")

    im = Image.open(base_path).convert("RGBA")
    draw = ImageDraw.Draw(im)

    ROW_Y = [375, 650, 925, 1200, 1475]
    NAME_FONT = font(58)
    DATA_FONT = font(48)

    for i, user in enumerate(users[:5]):
        username = f"User {user['user_id']}"
        xp = user.get("xp_total", 0)
        wins = user.get("wins", 0)
        fights = user.get("mobs_defeated", 0)

        y = ROW_Y[i]

        # USERNAME
        draw.text((250, y), username, fill="black", font=NAME_FONT)

        # XP + FIGHTS/WINS
        draw.text(
            (250, y + 90),
            f"XP: {xp}     F/W: {fights} / {wins}",
            fill="black",
            font=DATA_FONT
        )

    out = "/tmp/leaderboard.png"
    im.save(out)
    return out
