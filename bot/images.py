# bot/images.py
# MegaGrok Premium Comic Leaderboard Renderer (fixed)
# Resolution: 1080x1920 — Telegram-optimized
# Uses draw.textbbox (Pillow 8+) for text measurement to avoid textsize issues.

from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageFilter
import math
import os

# Canvas
WIDTH = 1080
HEIGHT = 1920

# Colors
BACKGROUND_COLOR = (18, 18, 20)   # dark graphite
TITLE_COLOR = (255, 184, 77)      # gold/orange
USERNAME_COLOR = (142, 240, 255)  # neon cyan
STAT_COLOR = (255, 184, 77)       # gold for LV • XP
RANK_WHITE = (255, 255, 255)

# Fonts: try to use a custom font path, fallback to DejaVu
FONT_FOLDER = "assets/fonts"
PREFERRED_FONT = os.path.join(FONT_FOLDER, "Megagrok.ttf")  # your packaged font
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Layout
MAX_USERNAME_LEN = 18
START_Y = 360
ROW_HEIGHT = 200
ROW_GAP = 20
LEFT_MARGIN = 80
BURST_SIZE = 160
TEXT_OFFSET_X = LEFT_MARGIN + BURST_SIZE + 40
TITLE_Y = 80

# Burst and strip colors
BURST_COLORS = [
    "#FFD700",  # gold
    "#C0C0C0",  # silver
    "#CD7F32",  # bronze
]
DEFAULT_BURST = "#2E2E2E"
STRIP_COLORS = [
    (80, 60, 0),
    (60, 60, 60),
    (80, 45, 20)
]
STRIP_DEFAULT = (40, 40, 40)


# ---------------------------
# Helpers
# ---------------------------
def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        try:
            return ImageFont.truetype(FALLBACK_FONT, size=size)
        except Exception:
            return ImageFont.load_default()


def _truncate_username(name: str, max_len=MAX_USERNAME_LEN):
    if not isinstance(name, str):
        name = str(name)
    if len(name) <= max_len:
        return name
    if max_len <= 1:
        return name[:max_len]
    return name[: max_len - 1] + "…"


def _text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont):
    """
    Return (w,h) using textbbox which is more reliable across Pillow versions.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return (w, h)


# ---------------------------
# Burst drawing
# ---------------------------
def _explosion_points(cx, cy, outer_r, inner_r, spikes=12, rotation=0.0):
    pts = []
    total = spikes * 2
    for i in range(total):
        angle = rotation + (i * math.pi * 2) / total
        r = outer_r if (i % 2 == 0) else inner_r
        x = cx + math.cos(angle) * r
        y = cy + math.sin(angle) * r
        pts.append((x, y))
    return pts


def _draw_burst(draw: ImageDraw.Draw, cx, cy, outer_r, inner_r, color_hex, outline=(0, 0, 0), spikes=14):
    # polygon points
    pts = _explosion_points(cx, cy, outer_r, inner_r, spikes=spikes)
    draw.polygon(pts, fill=ImageColor.getrgb(color_hex), outline=outline)
    # inner circle (white)
    inner_box = [cx - inner_r * 0.6, cy - inner_r * 0.6, cx + inner_r * 0.6, cy + inner_r * 0.6]
    draw.ellipse(inner_box, fill=(255, 255, 255), outline=outline)


def _draw_rank_number(draw: ImageDraw.Draw, cx, cy, rank, font):
    txt = str(rank)
    tw, th = _text_size(draw, txt, font)
    # black outline by drawing multiple offsets
    offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2)]
    for ox, oy in offsets:
        draw.text((cx - tw / 2 + ox, cy - th / 2 + oy), txt, font=font, fill=(0, 0, 0))
    draw.text((cx - tw / 2, cy - th / 2), txt, font=font, fill=RANK_WHITE)


# ---------------------------
# Halftone subtle overlay
# ---------------------------
def _halftone_overlay(size, spacing=18, radius=1, color=(255, 255, 255, 6)):
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(layer)
    for y in range(0, h, spacing):
        for x in range(0, w, spacing):
            dd.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return layer.filter(ImageFilter.GaussianBlur(0.2))


# ---------------------------
# Main generation function
# ---------------------------
def generate_leaderboard_premium(users, output_path="/tmp/leaderboard_premium.png", max_rows=12):
    """
    users: list of dicts, ordered top-first:
      {"user_id":..., "username": "...", "level": int, "xp_total": int}
    Returns: path to PNG
    """

    # Prepare canvas
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(canvas)

    # fonts
    font_title = _load_font(PREFERRED_FONT, 120)
    font_name = _load_font(PREFERRED_FONT, 64)
    font_stats = _load_font(PREFERRED_FONT, 44)
    font_rank = _load_font(PREFERRED_FONT, 48)
    font_rank_small = _load_font(PREFERRED_FONT, 40)

    # subtle halftone overlay
    try:
        ht = _halftone_overlay((WIDTH, HEIGHT), spacing=20, radius=1)
        canvas = Image.alpha_composite(canvas.convert("RGBA"), ht).convert("RGB")
        draw = ImageDraw.Draw(canvas)
    except Exception:
        # ignore halftone errors
        draw = ImageDraw.Draw(canvas)

    # title (centered)
    title = "MEGAGROK\nLEADERBOARD"
    # compute title size and center
    t_w, t_h = draw.multiline_textbbox((0, 0), title, font=font_title)[2:4]
    title_x = (WIDTH - t_w) // 2
    draw.multiline_text((title_x, TITLE_Y), title, font=font_title, fill=TITLE_COLOR, align="center")

    # rows (clamped)
    rows = users[:max_rows]

    y = START_Y

    for idx, u in enumerate(rows):
        rank = idx + 1
        username = u.get("username") or f"User{u.get('user_id')}"
        level = u.get("level", u.get("lvl", 1))
        xp = u.get("xp_total", u.get("xp", 0))

        # row strip background (rounded rectangle: approximate with rectangle since pillow rounded may be absent)
        left = LEFT_MARGIN
        right = WIDTH - LEFT_MARGIN
        top = y
        bottom = y + ROW_HEIGHT - ROW_GAP

        # strip color
        if rank <= 3:
            strip_color = STRIP_COLORS[rank - 1]
            burst_color = BURST_COLORS[rank - 1]
        else:
            strip_color = STRIP_DEFAULT
            burst_color = DEFAULT_BURST

        # draw strip rectangle
        draw.rectangle([left, top, right, bottom], fill=strip_color)

        # burst center coords
        burst_cx = left + BURST_SIZE // 2
        burst_cy = top + (bottom - top) // 2

        # draw burst and rank
        _draw_burst(draw, burst_cx, burst_cy, BURST_SIZE // 2 + 10, BURST_SIZE // 4, burst_color, outline=(0, 0, 0), spikes=14)
        # rank number - use smaller font for center
        _draw_rank_number(draw, burst_cx, burst_cy, rank, font_rank_small)

        # username (truncate)
        uname = _truncate_username(username, max_len=MAX_USERNAME_LEN)

        # compute name position; ensure no overlap with burst
        name_x = TEXT_OFFSET_X
        name_y = top + 30

        # draw black outline for username for pop
        offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2)]
        for ox, oy in offsets:
            draw.text((name_x + ox, name_y + oy), uname, font=font_name, fill=(0, 0, 0))
        draw.text((name_x, name_y), uname, font=font_name, fill=USERNAME_COLOR)

        # stats line: LV 23 • 149 XP (gold color)
        stats_txt = f"LV {int(level)} \u2022 {int(xp)} XP"
        stats_x = name_x
        stats_y = name_y + 72
        draw.text((stats_x, stats_y), stats_txt, font=font_stats, fill=STAT_COLOR)

        # increment y
        y += ROW_HEIGHT

    # footer
    footer = "t.me/megagrok  •  MegaGrok Metaverse"
    fw, fh = _text_size(draw, footer, font=_load_font(PREFERRED_FONT, 28))
    draw.text(((WIDTH - fw) // 2, HEIGHT - 80), footer, font=_load_font(PREFERRED_FONT, 28), fill=(107, 107, 107))

    # save
    try:
        canvas.save(output_path, quality=90)
    except Exception as e:
        # fallback location if permission issues
        alt = "/tmp/leaderboard_premium.png"
        canvas.save(alt, quality=90)
        return alt

    return output_path
