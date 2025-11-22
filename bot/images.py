import os
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = "assets"

# Base templates
PROFILE_BASE = "profile_base.png"
LEADERBOARD_BASE = "leaderboard_base.png"

SPRITES = {
    "Tadpole": "tadpole.png",
    "Hopper": "hopper.png",
    "Ascended": "ascended.png",
}

# -------------------------------------------------------
# FONT LOADER
# -------------------------------------------------------
def load_font(name: str, size: int):
    path = os.path.join(ASSET_DIR, name)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT_BOLD = load_font("Roboto-Bold.ttf", 72)
FONT_REG = load_font("Roboto-Regular.ttf", 44)
FONT_LABEL = load_font("Roboto-Regular.ttf", 36)
FONT_NUM = load_font("Roboto-Bold.ttf", 70)
FONT_SMALL = load_font("Roboto-Light.ttf", 26)

# -------------------------------------------------------
# HELPER
# -------------------------------------------------------
def outline_text(draw, xy, text, font, fill, outline, stroke=3, anchor=None):
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor
    )


def load_image(filename: str) -> Optional[Image.Image]:
    path = os.path.join(ASSET_DIR, filename)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return None


# -------------------------------------------------------
# PROFILE GENERATOR
# -------------------------------------------------------
def generate_profile_image(user: Dict[str, Any]) -> str:
    uid = user.get("user_id", "unknown")
    username = user.get("username", f"User {uid}")
    form = user.get("form", "Tadpole")
    level = int(user.get("level", 1))
    fights = int(user.get("fights", user.get("mobs_defeated", 0)))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    tg = user.get("tg", "t.me/megagrok")
    ca = user.get("ca", "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump")

    base = load_image(PROFILE_BASE)
    if base is None:
        base = Image.new("RGBA", (900, 1280), (255, 255, 255, 255))

    draw = ImageDraw.Draw(base)
    W, H = base.size

    # --------------------------------------
    # HEADER: MEGAGROK + username
    # --------------------------------------
    title = "MEGAGROK"
    tw, th = draw.textsize(title, font=FONT_BOLD)
    draw.text(((W - tw) / 2, 40), title, font=FONT_BOLD, fill=(20, 20, 20))

    uw, uh = draw.textsize(username, font=FONT_REG)
    draw.text(((W - uw) / 2, 130), username, font=FONT_REG, fill=(20, 20, 20))

    # --------------------------------------
    # SPRITE IN CENTER BOX
    # --------------------------------------
    sprite = load_image(SPRITES.get(form, "tadpole.png"))
    if sprite:
        box_left, box_top = 70, 200
        box_w = W - 140
        target_w = int(box_w * 0.55)

        aspect = sprite.height / sprite.width
        target_h = int(target_w * aspect)

        sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

        sx = 70 + (box_w - target_w) // 2
        sy = 200 + 20
        base.paste(sprite, (sx, sy), sprite)

    # --------------------------------------
    # STATS BOXES (Level | Fights/Wins | Rituals)
    # Pixel-perfect alignment for your template
    # --------------------------------------

    # Box positions on your profile_base.png
    # (measured directly from template)
    LEFT = (80, 880, 280, 1020)
    MID = (300, 880, 600, 1020)
    RIGHT = (620, 880, 820, 1020)

    # LEVEL (centered)
    lw = draw.textsize("LEVEL", font=FONT_LABEL)[0]
    draw.text((LEFT[0] + (200 - lw) / 2, LEFT[1] + 5),
              "LEVEL", font=FONT_LABEL, fill=(20,20,20))

    ln = str(level)
    lnw = draw.textsize(ln, font=FONT_NUM)[0]
    draw.text((LEFT[0] + (200 - lnw) / 2, LEFT[1] + 55),
              ln, font=FONT_NUM, fill=(20,20,20))

    # FIGHTS / WINS (centered in MID box)
    fw_label = "FIGHTS / WINS"
    fw_w = draw.textsize(fw_label, font=FONT_LABEL)[0]
    draw.text((MID[0] + (300 - fw_w) / 2, MID[1] + 5),
              fw_label, font=FONT_LABEL, fill=(20,20,20))

    fw_val = f"{fights} / {wins}"
    fwv_w = draw.textsize(fw_val, font=FONT_NUM)[0]
    draw.text((MID[0] + (300 - fwv_w) / 2, MID[1] + 55),
              fw_val, font=FONT_NUM, fill=(20,20,20))

    # RITUALS (centered)
    rw = draw.textsize("RITUALS", font=FONT_LABEL)[0]
    draw.text((RIGHT[0] + (200 - rw) / 2, RIGHT[1] + 5),
              "RITUALS", font=FONT_LABEL, fill=(20,20,20))

    rv = str(rituals)
    rvw = draw.textsize(rv, font=FONT_NUM)[0]
    draw.text((RIGHT[0] + (200 - rvw) / 2, RIGHT[1] + 55),
              rv, font=FONT_NUM, fill=(20,20,20))

    # --------------------------------------
    # FOOTER (TG / CA)
    # --------------------------------------
    tg_w = draw.textsize(f"TG: {tg}", font=FONT_SMALL)[0]
    ca_w = draw.textsize(f"CA: {ca}", font=FONT_SMALL)[0]

    draw.text(((W - tg_w) / 2, 1130), f"TG: {tg}", font=FONT_SMALL, fill=(20,20,20))
    draw.text(((W - ca_w) / 2, 1165), f"CA: {ca}", font=FONT_SMALL, fill=(20,20,20))

    # save
    out = f"/tmp/profile_{uid}.png"
    base.save(out)
    return out


# -------------------------------------------------------
# LEADERBOARD GENERATOR
# -------------------------------------------------------
def generate_leaderboard_image() -> str:
    from bot.db import get_top_users

    base = load_image(LEADERBOARD_BASE)
    if base is None:
        base = Image.new("RGBA", (1000, 1600), (255,255,255,255))

    draw = ImageDraw.Draw(base)
    W, H = base.size

    # Title
    title = "TOP 5 LEADERBOARD"
    tw = draw.textsize(title, FONT_BOLD)[0]
    draw.text(((W - tw)/2, 40), title, font=FONT_BOLD, fill=(20,20,20))

    users = get_top_users(5)

    # row vertical positions matched to your template
    row_y_positions = [260, 460, 660, 860, 1060]

    for i, (user, row_y) in enumerate(zip(users, row_y_positions)):
        rank = i + 1

        # Rank number inside the circle (circle exists in base)
        rk = str(rank)
        rkw = draw.textsize(rk, font=FONT_NUM)[0]
        draw.text((110 - rkw/2, row_y + 10), rk, font=FONT_NUM, fill=(20,20,20))

        # Sprite
        sprite = load_image(SPRITES.get(user["form"], "tadpole.png"))
        if sprite:
            sprite = sprite.resize((150,150))
            base.paste(sprite, (170, row_y - 10), sprite)

        # Username
        uname = user.get("username", f"User{user['user_id']}")
        draw.text((350, row_y), uname, font=FONT_REG, fill=(20,20,20))

        # XP + fights/wins
        xp = user.get("xp_total", 0)
        fights = user.get("mobs_defeated", 0)
        wins = user.get("wins", 0)

        line2 = f"XP: {xp}    FIGHTS / WINS: {fights} / {wins}"
        draw.text((350, row_y + 50), line2, font=FONT_LABEL, fill=(20,20,20))

    out = "/tmp/leaderboard.png"
    base.save(out)
    return out
