# bot/images.py
# Leaderboard + Profile image generator (Pillow)

import os
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------
# FONT SETUP
# -------------------------------------------------------------
FONT_TITLE = "/usr/local/share/fonts/megagrok.ttf"
FONT_BODY = "/usr/local/share/fonts/megagrok.ttf"

if not os.path.exists(FONT_TITLE):
    # fallback
    FONT_TITLE = FONT_BODY = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _load_font(size):
    try:
        return ImageFont.truetype(FONT_BODY, size)
    except:
        return ImageFont.load_default()


# -------------------------------------------------------------
# DRAWING HELPERS
# -------------------------------------------------------------

def _text(draw, text, xy, size, fill):
    font = _load_font(size)
    draw.text(xy, text, font=font, fill=fill)


def _bbox(draw, text, size):
    font = _load_font(size)
    return draw.textbbox((0, 0), text, font=font)


def _medal_icon(draw, x, y, size, fill_color, outline="black"):
    """
    Draws a comic-style circular medal with a star.
    size = diameter
    """
    r = size // 2
    # Circle
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill_color, outline=outline, width=4)
    # Star (simple 5-point style)
    star = [
        (x, y - r + 6),
        (x + r - 4, y + r - 8),
        (x - r + 4, y + r - 8),
    ]
    draw.polygon(star, fill="white", outline=outline)


# -------------------------------------------------------------
# LEADERBOARD GENERATOR
# -------------------------------------------------------------

def generate_leaderboard_poster_v2(users, output_path="/tmp/leaderboard.png"):
    """
    users = [(user_id, username, xp), ...] sorted descending by XP
    Writes image file to output_path
    """

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#1a1a1d")
    draw = ImageDraw.Draw(img)

    # Title
    title = "MEGAGROK\nLEADERBOARD"
    title_font = _load_font(140)
    title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font)
    tw = title_bbox[2] - title_bbox[0]
    draw.multiline_text(
        ((W - tw) // 2, 80),
        title,
        font=title_font,
        fill="#ff9933",
        align="center"
    )

    # Y offset under title
    y = 400

    # Row settings
    row_h = 150
    padding = 20

    for idx, (uid, uname, xp) in enumerate(users[:50]):  # max 50 entries
        rank = idx + 1

        # fallback username
        if not uname:
            uname = f"User{uid}"

        # Determine style for top 3
        medal_color = None
        strip_color = None

        if rank == 1:
            medal_color = "#ffd700"      # Gold
            strip_color = "#3a2a00"
        elif rank == 2:
            medal_color = "#c0c0c0"      # Silver
            strip_color = "#2e2e2e"
        elif rank == 3:
            medal_color = "#cd7f32"      # Bronze
            strip_color = "#3b2415"

        # Draw colored strip behind top 3
        if strip_color:
            draw.rectangle(
                (60, y - 20, W - 60, y + row_h - 50),
                fill=strip_color
            )

        # Draw medal
        if medal_color:
            _medal_icon(draw, 140, y + 40, 80, medal_color)

        # Rank text
        _text(draw, f"{rank}", (240, y), 70, "#ffffff")

        # Username
        _text(draw, uname, (350, y), 70, "#8df0ff")

        # XP text
        _text(draw, f"{xp} XP", (350, y + 70), 50, "#ffcc66")

        y += row_h

    img.save(output_path)
    return output_path


# -------------------------------------------------------------
# PROFILE IMAGE (placeholder until we finalize new design)
# -------------------------------------------------------------
def generate_profile_image(user):
    """
    Placeholder until we rebuild profile card v2.
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), "#202024")
    draw = ImageDraw.Draw(img)

    uname = user.get("username", f"User{user['user_id']}")
    xp = user.get("xp_total", 0)
    lvl = user.get("level", 1)

    _text(draw, uname, (60, 60), 80, "#8df0ff")
    _text(draw, f"Level {lvl}", (60, 180), 60, "#ff9933")
    _text(draw, f"XP: {xp}", (60, 260), 60, "#ffffff")

    path = f"/tmp/profile_{user['user_id']}.png"
    img.save(path)
    return path
