# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont
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

TITLE_FONT = load_font(64)
HEADER_FONT = load_font(44)
STAT_FONT = load_font(34)
SMALL_FONT = load_font(24)


# ---------------------------------------------------
# Outline text (comic style)
# ---------------------------------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=4, anchor=None):
    draw.text(
        pos,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor
    )


# ---------------------------------------------------
# Sprite loader
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
# TRADING CARD PROFILE
# ---------------------------------------------------
def generate_profile_image(user):
    """
    Vertical trading card, perfect for sharing.
    Shows:
      - Title ribbon
      - User ID
      - Level
      - Big Grok sprite centered
      - Stats panel
    """

    # Extract fields
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

    # ---------------------------------------------------
    # Canvas
    # ---------------------------------------------------
    WIDTH, HEIGHT = 900, 1280
    bg_color = (245, 240, 230)  # warm paper
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(canvas)

    # ---------------------------------------------------
    # Comic Border
    # ---------------------------------------------------
    M = 30
    outer = (M, M, WIDTH-M, HEIGHT-M)

    # Thick black border
    draw.rectangle(outer, outline=(0,0,0), width=12)

    # Yellow inset
    inset = 14
    yellow_frame = (
        outer[0]+inset,
        outer[1]+inset,
        outer[2]-inset,
        outer[3]-inset
    )
    draw.rectangle(yellow_frame, outline=(255,220,80), width=10)

    # Inner black line
    inner_frame = (
        yellow_frame[0]+10,
        yellow_frame[1]+10,
        yellow_frame[2]-10,
        yellow_frame[3]-10
    )
    draw.rectangle(inner_frame, outline=(0,0,0), width=4)

    # ---------------------------------------------------
    # Header Title
    # ---------------------------------------------------
    outline_text(
        draw,
        (WIDTH//2, inner_frame[1] + 60),
        "MEGAGROK TRADING CARD",
        TITLE_FONT,
        fill=(255,245,200),
        outline=(40,10,80),
        stroke=6,
        anchor="mm"
    )

    # Username + level
    outline_text(
        draw,
        (WIDTH//2, inner_frame[1] + 150),
        f"User {user_id}",
        HEADER_FONT,
        fill=(40,40,40),
        outline=(255,255,255),
        stroke=4,
        anchor="mm"
    )

    outline_text(
        draw,
        (WIDTH//2, inner_frame[1] + 210),
        f"Level {level}",
        HEADER_FONT,
        fill=(40,40,40),
        outline=(255,255,255),
        stroke=4,
        anchor="mm"
    )

    # ---------------------------------------------------
    # Center Sprite
    # ---------------------------------------------------
    sprite = load_form_image(form)
    hero_y = inner_frame[1] + 270

    if sprite:
        sp = sprite.resize((520, 520)).convert("RGBA")
        sx = WIDTH//2 - sp.width//2
        canvas.paste(sp, (sx, hero_y), sp)
    else:
        # fallback circle
        draw.ellipse([WIDTH//2 - 200, hero_y, WIDTH//2 + 200, hero_y + 400],
                     fill=(90,90,90))
        outline_text(draw, (WIDTH//2, hero_y + 200), "??",
                     HEADER_FONT, anchor="mm")

    # ---------------------------------------------------
    # Stats Panel (bottom box)
    # ---------------------------------------------------
    stats_h = 320
    stats_rect = (
        inner_frame[0] + 40,
        inner_frame[3] - stats_h - 40,
        inner_frame[2] - 40,
        inner_frame[3] - 40
    )
    draw.rounded_rectangle(stats_rect, radius=24,
                           fill=(255,252,230),
                           outline=(0,0,0), width=6)

    sx = stats_rect[0] + 40
    sy = stats_rect[1] + 40

    # XP row
    outline_text(
        draw, (sx, sy),
        f"XP  {xp_current}/{xp_next}   ({int(pct*100)}%)",
        STAT_FONT, fill=(50,50,50), outline=(255,255,255), stroke=2
    )

    sy += 70

    # Lifetime XP
    outline_text(
        draw, (sx, sy),
        f"Lifetime XP: {xp_total}",
        STAT_FONT, fill=(50,50,50), outline=(255,255,255), stroke=2
    )

    sy += 70

    # Wins / Mobs / Rituals
    outline_text(draw, (sx, sy),        f"Wins: {wins}",
                 STAT_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (sx + 250, sy), f"Mobs: {mobs}",
                 STAT_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (sx + 480, sy), f"Rituals: {rituals}",
                 STAT_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)

    # ---------------------------------------------------
    # Save
    # ---------------------------------------------------
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# ---------------------------------------------------
# SIMPLE LEADERBOARD
# ---------------------------------------------------
def generate_leaderboard_image():
    users = get_top_users()
    width = 900
    row_h = 120
    height = 200 + len(users)*row_h

    canvas = Image.new("RGBA", (width, height), (240,240,240,255))
    draw = ImageDraw.Draw(canvas)

    outline_text(
        draw, (width//2, 80),
        "MEGAGROK HOP-FAME",
        TITLE_FONT,
        fill=(30,30,30),
        outline=(255,255,255),
        stroke=5,
        anchor="mm"
    )

    y = 160
    for rank, user in enumerate(users, 1):
        uid = user.get("user_id", "?")
        level = user.get("level", 1)
        xp_total = user.get("xp_total", 0)
        form = user.get("form", "Tadpole")

        draw.rectangle([(40, y), (width-40, y+row_h-20)],
                       outline=(0,0,0), width=4, fill=(255,255,255))

        outline_text(draw, (70, y+40), f"#{rank}",
                     HEADER_FONT, fill=(20,20,20), outline=(255,255,255), stroke=4)

        sprite = load_form_image(form)
        if sprite:
            sp = sprite.resize((100,100))
            canvas.paste(sp, (160, y+10), sp)

        draw.text((300, y+30), f"User {uid}", font=STAT_FONT, fill=(20,20,20))
        draw.text((300, y+75), f"Lvl {level} — {xp_total} XP", font=SMALL_FONT, fill=(40,40,40))

        y += row_h

    out = "/tmp/leaderboard.png"
    canvas.save(out)
    return out
