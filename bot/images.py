# bot/images.py
# MegaGrok Premium Comic Leaderboard Renderer
# Resolution: 1080x1920 — Telegram-optimized
# Uses comic bursts, username truncation, LV • XP formatting.

from PIL import Image, ImageDraw, ImageFont
import os

WIDTH = 1080
HEIGHT = 1920

BACKGROUND_COLOR = (16, 16, 20)  # MegaGrok dark graphite
TITLE_COLOR = (255, 184, 77)     # Gold-orange comic title
USERNAME_COLOR = (142, 255, 255) # Neon cyan
STAT_COLOR = (255, 184, 77)      # Gold stats

FONT_FOLDER = "assets/fonts"
TITLE_FONT = os.path.join(FONT_FOLDER, "Megagrok.ttf")
TEXT_FONT = os.path.join(FONT_FOLDER, "Megagrok.ttf")

MAX_USERNAME_LEN = 18  # hard truncate for Option A


# -------------------------------------------
# Helpers
# -------------------------------------------

def truncate_username(name: str, max_len=MAX_USERNAME_LEN):
    if len(name) <= max_len:
        return name
    return name[:max_len - 1] + "…"


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size=size)
    except:
        return ImageFont.load_default()


# -------------------------------------------
# Burst medal drawing
# -------------------------------------------

def draw_burst(draw: ImageDraw.Draw, x, y, size, color, rank_num):
    """
    Draws a comic explosion burst medal with a rank number inside.
    """
    cx = x + size // 2
    cy = y + size // 2

    # Burst spikes
    spikes = 18
    outer_r = size // 2
    inner_r = size // 3

    points = []
    for i in range(spikes * 2):
        angle = 3.14159 * i / spikes
        r = outer_r if i % 2 == 0 else inner_r
        px = cx + int(r * 1.1 * (1.1 if i % 2 == 0 else 1.0) * (1 if i % 4 < 2 else -1) * abs(round(__import__("math").cos(angle), 5)))
        py = cy + int(r * (1 if i % 4 < 2 else -1) * abs(round(__import__("math").sin(angle), 5)))
        points.append((px, py))

    draw.polygon(points, fill=color, outline=(0, 0, 0))

    # Inner circle
    inner_color = (255, 255, 255)
    draw.ellipse([x + size * 0.25, y + size * 0.25, x + size * 0.75, y + size * 0.75], fill=inner_color, outline=(0, 0, 0))

    # Rank number
    font = load_font(TEXT_FONT, int(size * 0.35))
    text = str(rank_num)
    tw, th = draw.textsize(text, font=font)
    draw.text((cx - tw // 2, cy - th // 2), text, fill=(0, 0, 0), font=font)


# -------------------------------------------
# Leaderboard renderer
# -------------------------------------------

def generate_leaderboard_premium(users, output_path="/tmp/leaderboard.png"):
    """
    users: list of dicts [{user_id, username, level, xp_total}]
    """

    img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = load_font(TITLE_FONT, 140)
    font_name = load_font(TEXT_FONT, 70)
    font_stats = load_font(TEXT_FONT, 55)

    # -------------------------------------------
    # Title
    # -------------------------------------------
    title = "MEGAGROK\nLEADERBOARD"
    draw.multiline_text(
        (WIDTH // 2, 140),
        title,
        fill=TITLE_COLOR,
        font=font_title,
        anchor="ma",
        align="center"
    )

    # -------------------------------------------
    # Row settings
    # -------------------------------------------
    start_y = 400
    row_height = 200
    burst_size = 160
    left_margin = 80
    text_offset_x = left_margin + burst_size + 40

    # -------------------------------------------
    # Rank colors
    # -------------------------------------------
    burst_colors = [
        (255, 215, 0),     # gold
        (200, 200, 200),   # silver
        (205, 127, 50)     # bronze
    ]
    default_burst = (120, 120, 120)  # grey for 4th+

    strip_colors = [
        (80, 60, 0),
        (60, 60, 60),
        (80, 45, 20)
    ]
    strip_default = (40, 40, 40)

    # -------------------------------------------
    # Draw each row
    # -------------------------------------------
    y = start_y

    for i, user in enumerate(users):
        rank = i + 1

        # Determine colors
        burst_color = burst_colors[i] if i < 3 else default_burst
        strip_color = strip_colors[i] if i < 3 else strip_default

        # Strip background
        draw.rectangle(
            [left_margin, y, WIDTH - left_margin, y + row_height - 20],
            fill=strip_color,
            outline=None
        )

        # Draw burst medal
        draw_burst(draw, left_margin - 20, y + 20, burst_size, burst_color, rank)

        # Username (truncate if needed)
        raw_name = user.get("username") or f"User{user.get('user_id')}"
        name = truncate_username(raw_name)
        draw.text(
            (text_offset_x, y + 40),
            name,
            fill=USERNAME_COLOR,
            font=font_name
        )

        # Stats: LV • XP
        level = user.get("level", 1)
        xp = user.get("xp_total", 0)
        stats = f"LV {level} • {xp} XP"

        draw.text(
            (text_offset_x, y + 120),
            stats,
            fill=STAT_COLOR,
            font=font_stats
        )

        y += row_height + 20

    img.save(output_path)
    return output_path
