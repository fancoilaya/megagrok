# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont
from bot.db import get_top_users

ASSET_DIR = "assets"


# ---------------------------------------------------
# FONT LOADING (SAFE FALLBACK)
# ---------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = load_font(56)
HERO_FONT  = load_font(40)
BODY_FONT  = load_font(26)
SMALL_FONT = load_font(18)


# ---------------------------------------------------
# OUTLINE TEXT HELPER
# ---------------------------------------------------
def outline_text(draw, xy, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor
    )


# ---------------------------------------------------
# GROK SPRITE LOADER
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
# CLEAN MINIMAL PROFILE GENERATOR
# ---------------------------------------------------
def generate_profile_image(user):
    """
    Minimal clean profile:
      - User name
      - Level
      - Centered Grok sprite
    No effects, no fog, no overlays, no borders.
    """

    user_id = user.get("user_id", "unknown")
    level = int(user.get("level", 1))
    form = user.get("form", "Tadpole")

    WIDTH, HEIGHT = 900, 1100
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (240, 240, 240, 255))
    draw = ImageDraw.Draw(canvas)

    # Title
    outline_text(
        draw,
        (WIDTH // 2, 80),
        "MegaGrok",
        TITLE_FONT,
        fill=(20,20,20),
        outline=(255,255,255),
        stroke=5,
        anchor="mm"
    )

    # Username
    outline_text(
        draw,
        (WIDTH // 2, 180),
        f"User: {user_id}",
        HERO_FONT,
        fill=(40,40,40),
        outline=(255,255,255),
        stroke=4,
        anchor="mm"
    )

    # Level
    outline_text(
        draw,
        (WIDTH // 2, 250),
        f"Level {level}",
        HERO_FONT,
        fill=(40,40,40),
        outline=(255,255,255),
        stroke=4,
        anchor="mm"
    )

    # Sprite
    sprite = load_form_image(form)
    if sprite:
        sp = sprite.resize((500, 500)).convert("RGBA")
        sx = WIDTH // 2 - sp.width // 2
        sy = 360
        canvas.paste(sp, (sx, sy), sp)
    else:
        draw.ellipse([WIDTH//2 - 150, 500, WIDTH//2 + 150, 800], fill=(90,90,90))
        outline_text(draw, (WIDTH//2, 650), "??", HERO_FONT,
                     fill=(255,255,255), outline=(0,0,0), stroke=4, anchor="mm")

    # Save
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# ---------------------------------------------------
# SIMPLE LEADERBOARD IMAGE
# ---------------------------------------------------
def generate_leaderboard_image():
    users = get_top_users()

    WIDTH = 900
    ROW_H = 120
    HEIGHT = 150 + len(users) * ROW_H

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (240, 240, 240, 255))
    draw = ImageDraw.Draw(canvas)

    # Title
    outline_text(
        draw,
        (WIDTH // 2, 60),
        "MEGAGROK LEADERBOARD",
        TITLE_FONT,
        fill=(30,30,30),
        outline=(255,255,255),
        stroke=5,
        anchor="mm"
    )

    y = 150
    for rank, user in enumerate(users, start=1):

        uid = user.get("user_id", "?")
        level = user.get("level", 1)
        xp = user.get("xp_total", user.get("xp", 0))
        form = user.get("form", "Tadpole")

        # Row background
        draw.rectangle(
            [(40, y), (WIDTH - 40, y + ROW_H - 20)],
            fill=(255,255,255),
            outline=(0,0,0),
            width=2
        )

        # Rank number
        outline_text(
            draw,
            (70, y + 40),
            f"#{rank}",
            HERO_FONT,
            fill=(20,20,20),
            outline=(255,255,255),
            stroke=4
        )

        # Sprite
        sprite = load_form_image(form)
        if sprite:
            sp = sprite.resize((100, 100))
            canvas.paste(sp, (160, y + 10), sp)

        # User + stats
        draw.text((300, y + 25), f"User {uid}", font=BODY_FONT, fill=(20,20,20))
        draw.text((300, y + 60), f"Lvl {level} — {xp} XP", font=SMALL_FONT, fill=(30,30,30))

        y += ROW_H

    out = "/tmp/leaderboard.png"
    canvas.save(out)
    return out
