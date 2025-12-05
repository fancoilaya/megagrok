# bot/images.py
# MegaGrok Leaderboard Poster Generator (Pillow 10+ Compatible)

import os
from PIL import Image, ImageDraw, ImageFont


# -------------------------------------------------
# FONT SETUP
# -------------------------------------------------
FONT_PATH = "/usr/local/share/fonts/megagrok.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()


# -------------------------------------------------
# DRAW HELPERS
# -------------------------------------------------
def _draw_medal(draw, x, y, size, fill):
    """Comic-style medal with thick outline + simple star."""
    r = size // 2
    draw.ellipse(
        (x - r, y - r, x + r, y + r),
        fill=fill,
        outline="black",
        width=6,
    )

    # Star (simple 3-point comic star)
    star = [
        (x, y - r + 8),
        (x + r - 6, y + r - 10),
        (x - r + 6, y + r - 10),
    ]
    draw.polygon(star, fill="white", outline="black")


# -------------------------------------------------
# MAIN POSTER GENERATOR (FIXED FOR PILLOW 10+)
# -------------------------------------------------
def generate_leaderboard_poster_v2(users, output_path="/tmp/leaderboard.png"):
    """
    users = list of dicts from db.get_top_users()
    """

    # Canvas
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "#191A1D")
    draw = ImageDraw.Draw(img)

    # -------------------------------------------------
    # TITLE (Pillow 10 fix)
    # -------------------------------------------------
    title = "MEGAGROK\nLEADERBOARD"
    font_title = _font(130)

    # Correct Pillow 10+ method:
    bbox = draw.multiline_textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]

    draw.multiline_text(
        ((W - tw) // 2, 60),
        title,
        font=font_title,
        fill="#FFB347",
        align="center",
    )

    # -------------------------------------------------
    # ROWS
    # -------------------------------------------------
    y = 350
    row_height = 150

    for idx, u in enumerate(users):
        rank = idx + 1

        uid = u["user_id"]
        uname = u["username"] or f"User{uid}"
        xp = u["xp_total"]

        # Top 3 highlighting
        medal = None
        strip = None

        if rank == 1:
            medal = "#FFD700"  # Gold
            strip = "#3A2A00"
        elif rank == 2:
            medal = "#C0C0C0"  # Silver
            strip = "#2E2E2E"
        elif rank == 3:
            medal = "#CD7F32"  # Bronze
            strip = "#3B2415"

        # Background strip
        if strip:
            draw.rectangle(
                (60, y - 20, W - 60, y + row_height - 40),
                fill=strip,
            )

        # Medal icon
        if medal:
            _draw_medal(draw, 140, y + 40, 90, medal)

        # Rank
        draw.text((240, y), f"{rank}", font=_font(70), fill="white")

        # Username
        draw.text((350, y), uname, font=_font(70), fill="#8DF0FF")

        # XP
        draw.text((350, y + 70), f"{xp} XP", font=_font(55), fill="#FFDD99")

        y += row_height

    img.save(output_path)
    return output_path
