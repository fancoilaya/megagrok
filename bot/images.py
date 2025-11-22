# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont
from bot.db import get_top_users

ASSET_DIR = "assets"

# --------------------------
# Font loader
# --------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

FONT_BIG = load_font(72)
FONT_MED = load_font(48)
FONT_SMALL = load_font(32)


# --------------------------------------------------------
# PROFILE CARD GENERATOR — USING BLANK TEMPLATE
# --------------------------------------------------------
def generate_profile_image(user):
    """
    Creates a trading-card style profile image using the blank template.
    Template path: assets/template_profile.png
    """

    template_path = os.path.join(ASSET_DIR, "template_profile.png")

    if not os.path.exists(template_path):
        raise FileNotFoundError("template_profile.png not found in assets/")

    # Load template
    card = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(card)

    # Read user data
    user_id = user.get("user_id", "unknown")
    username = user.get("username", f"User{user_id}")
    level = user.get("level", 1)
    wins = user.get("wins", 0)
    rituals = user.get("rituals", 0)

    # Evolution sprite
    form = user.get("form", "Tadpole")
    sprite_path = os.path.join(ASSET_DIR, f"{form.lower()}.png")

    if os.path.exists(sprite_path):
        sprite = Image.open(sprite_path).convert("RGBA")
        sprite = sprite.resize((650, 650), Image.LANCZOS)
        card.paste(sprite, (125, 260), sprite)

    # --------------------------
    # TEXT COORDINATES (fixed)
    # --------------------------
    # USERNAME
    draw.text((450, 110), username, font=FONT_BIG,
              fill="black", anchor="mm")

    # LEVEL
    draw.text((225, 1000), str(level),
              font=FONT_BIG, fill="black", anchor="mm")

    # WINS
    draw.text((450, 1000), str(wins),
              font=FONT_BIG, fill="black", anchor="mm")

    # RITUALS
    draw.text((675, 1000), str(rituals),
              font=FONT_BIG, fill="black", anchor="mm")

    # TG + CA
    tg = "t.me/megagrok"
    ca = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXir9g652pump"

    draw.text((450, 1135), f"TG: {tg}",
              font=FONT_SMALL, fill="black", anchor="mm")

    draw.text((450, 1180), f"CA: {ca}",
              font=FONT_SMALL, fill="black", anchor="mm")

    # Save
    out = f"/tmp/profile_{user_id}.png"
    card.save(out)
    return out


# --------------------------------------------------------
# LEADERBOARD — MATCHING STYLE (SIMPLE VERSION)
# --------------------------------------------------------
def generate_leaderboard_image():
    """
    Generates a leaderboard in a matching trading-card style.
    """

    users = get_top_users(10)
    width = 900
    height = 1500

    img = Image.new("RGBA", (width, height), (255, 249, 230, 255))
    draw = ImageDraw.Draw(img)

    title = "MEGAGROK — TOP 10"
    draw.text((width//2, 80), title, font=FONT_BIG,
              fill="black", anchor="mm")

    y = 200
    for i, u in enumerate(users):
        line = f"#{i+1}   User {u['user_id']}   Lvl {u['level']}   XP {u['xp_total']}"
        draw.text((80, y), line, font=FONT_MED, fill="black")
        y += 110

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
