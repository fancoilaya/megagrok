# bot/images.py
# MegaGrok Premium Comic Leaderboard (1080x1920)
# Style: MegaGrok Black + Explosion-burst medals (A3)
#
# Compatible with Pillow 10+ and db.get_top_users() returning a list of dicts:
#   [{"user_id":..., "username": "...", "xp_total": ...}, ...]
#
# Output path default: /tmp/leaderboard_premium.png

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------------------
# CONFIG
# ----------------------------
CANVAS_W = 1080
CANVAS_H = 1920
OUTPUT_PATH_DEFAULT = "/tmp/leaderboard_premium.png"

FONT_PATH = "/usr/local/share/fonts/megagrok.ttf"
if not os.path.exists(FONT_PATH):
    # fallback if the custom font isn't available
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Colors (MegaGrok palette)
BG_COLOR = "#121214"           # MegaGrok Black background
TITLE_COLOR = "#FFB347"       # Warm comic gold
USER_COLOR = "#8DF0FF"        # Cyan username
XP_COLOR = "#FFDFA0"          # XP color
RANK_COLOR = "#FFFFFF"

GOLD_BURST = "#FFD700"
SILVER_BURST = "#C0C0C0"
BRONZE_BURST = "#CD7F32"
GREY_BURST = "#2E2E2E"

STRIP_OPACITY = 220  # 0-255

# ----------------------------
# FONT HELPERS
# ----------------------------
def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

# ----------------------------
# DRAW HELPERS
# ----------------------------
def _multiline_text_size(draw, text, font):
    # Pillow 10+: use multiline_textbbox
    bbox = draw.multiline_textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])

def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])

def _center_x_for_text(draw, text, font, width):
    tw, _ = _text_size(draw, text, font)
    return (width - tw) // 2

# Explosion/burst polygon generator
def _explosion_points(cx, cy, outer_r, inner_r, spikes=12, rotation=0):
    pts = []
    angle_step = math.pi * 2 / (spikes * 2)
    for i in range(spikes * 2):
        angle = rotation + i * angle_step
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + math.cos(angle) * r
        y = cy + math.sin(angle) * r
        pts.append((x, y))
    return pts

def _draw_burst(draw, cx, cy, outer_r, inner_r, color, outline="#000000", outline_width=6, spikes=12):
    pts = _explosion_points(cx, cy, outer_r, inner_r, spikes=spikes)
    draw.polygon(pts, fill=color, outline=outline)
    # thick outline effect: draw again with no fill, just outline (Pillow draws outline around polygon)
    # outlined by the polygon call; we can also stroke by drawing smaller polygon with same outline, but fine.

def _halftone_overlay(size, dot_spacing=12, dot_radius=3, color=(255,255,255,10)):
    """Return an image with subtle halftone dots to overlay."""
    w, h = size
    halo = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(halo)
    for y in range(0, h, dot_spacing):
        for x in range(0, w, dot_spacing):
            d.ellipse((x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius), fill=color)
    return halo.filter(ImageFilter.GaussianBlur(0.4))

def _draw_rank_burst(draw, img, rank, x, y, burst_color):
    """
    Draw an explosion burst and the rank number in front.
    x,y is the center point for the burst.
    """
    outer = 110
    inner = 48
    _draw_burst(draw, x, y, outer, inner, burst_color, outline="#000000", outline_width=6, spikes=14)
    # draw white rank number with thick black stroke look:
    font_rank = _font(72)
    txt = str(rank)
    tw, th = _text_size(draw, txt, font_rank)
    # draw black outline by drawing text multiple times offset
    ox = x - tw // 2
    oy = y - th // 2 - 6
    # 1. black shadow multiple offsets
    shadow_offsets = [(-3,-3),(-3,3),(3,-3),(3,3)]
    for sx, sy in shadow_offsets:
        draw.text((ox+sx, oy+sy), txt, font=font_rank, fill="#000000")
    # 2. white front
    draw.text((ox, oy), txt, font=font_rank, fill="#FFFFFF")

# ----------------------------
# MAIN GENERATOR
# ----------------------------
def generate_leaderboard_premium(users, output_path=OUTPUT_PATH_DEFAULT, max_rows=12):
    """
    users: list of dicts from db.get_top_users(), expected keys:
      - user_id
      - username
      - xp_total
    Returns path to generated PNG.
    """

    # Canvas
    W, H = CANVAS_W, CANVAS_H
    canvas = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Slight vignette / background texture
    # Add subtle radial darker vignette
    vign = Image.new("RGBA", (W, H), (0,0,0,0))
    vd = ImageDraw.Draw(vign)
    # big semi-transparent radial ellipse to darken edges
    vd.ellipse((-W*0.2, -H*0.2, W*1.2, H*1.2), fill=(0,0,0,60))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), vign).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Halftone overlay (subtle)
    ht = _halftone_overlay((W,H), dot_spacing=18, dot_radius=2, color=(255,255,255,8))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), ht).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # TITLE
    title = "MEGAGROK\nLEADERBOARD"
    font_title = _font(120)
    bbox = draw.multiline_textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    # center top, slightly lowered to give space for bursts below
    title_x = (W - tw) // 2
    draw.multiline_text((title_x, 60), title, font=font_title, fill=TITLE_COLOR, align="center")
    # Drop shadow for title
    draw.multiline_text((title_x+6, 60+6), title, font=font_title, fill="#000000", align="center")

    # Setup rows
    start_y = 360
    row_h = 150
    gap = 24

    # clamp rows
    rows = users[:max_rows]

    # precompute maximal name width for layout
    sample_font = _font(64)

    # For each row draw:
    for idx, u in enumerate(rows):
        rank = idx + 1
        uid = u.get("user_id")
        uname = u.get("username") or f"User{uid}"
        xp = u.get("xp_total", 0)

        # coordinates
        row_top = start_y + idx * (row_h + gap)
        row_center_y = row_top + row_h // 2

        # determine burst & strip colors
        if rank == 1:
            burst_color = GOLD_BURST
            strip_color = (58,42,0, STRIP_OPACITY)  # darker gold strip
        elif rank == 2:
            burst_color = SILVER_BURST
            strip_color = (46,46,46, STRIP_OPACITY)
        elif rank == 3:
            burst_color = BRONZE_BURST
            strip_color = (59,36,21, STRIP_OPACITY)
        else:
            burst_color = GREY_BURST
            strip_color = (28,28,28, int(STRIP_OPACITY * 0.7))

        # Draw panel background for each row (rounded rectangle)
        pad_x = 64
        left = pad_x
        right = W - pad_x
        top = row_top
        bottom = row_top + row_h

        # rounded rectangle via polygon/ellipse combination
        r = 18
        draw.rounded_rectangle((left, top, right, bottom), radius=r, fill=strip_color)

        # For top 3, draw burst behind left area
        burst_cx = left + 130
        burst_cy = row_center_y
        if rank <= 3:
            _draw_burst(draw, burst_cx, burst_cy, outer_r=120, inner_r=44, color=burst_color, outline="#000000", outline_width=6, spikes=14)
            # subtle inner glow
            glow = Image.new("RGBA", (W, H), (0,0,0,0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((burst_cx-80, burst_cy-80, burst_cx+80, burst_cy+80), fill=(*ImageColor_get_rgb(burst_color), 28))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), glow).convert("RGB")
            draw = ImageDraw.Draw(canvas, "RGBA")
        else:
            # small grey burst for later ranks
            _draw_burst(draw, burst_cx, burst_cy, outer_r=70, inner_r=30, color="#222222", outline="#000000", outline_width=5, spikes=10)

        # Draw explosion-burst medal with rank number (center left)
        _draw_rank_burst_simple(draw=draw, rank=rank, cx=burst_cx, cy=burst_cy) if False else _draw_rank_burst_custom(draw, canvas, rank, burst_cx, burst_cy, rank)

        # Username and XP text positions (to the right of burst)
        name_x = left + 260
        name_y = row_center_y - 26

        # Title-like username (big)
        draw.text((name_x, name_y), uname, font=_font(64), fill=USER_COLOR)
        # text outline effect (draw black stroked version behind)
        # since Pillow lacks stroke for text reliably cross-version, emulate by drawing offsets
        offsets = [(-2,-2),(-2,2),(2,-2),(2,2)]
        for ox, oy in offsets:
            draw.text((name_x+ox, name_y+oy), uname, font=_font(64), fill="#000000")
        draw.text((name_x, name_y), uname, font=_font(64), fill=USER_COLOR)

        # XP on its own line under username
        xp_text = f"{xp} XP"
        xp_x = name_x
        xp_y = name_y + 64 + 6
        draw.text((xp_x, xp_y), xp_text, font=_font(44), fill=XP_COLOR)
        # subtle shadow below xp
        draw.text((xp_x+2, xp_y+2), xp_text, font=_font(44), fill="#000000")

        # Large rank number displayed left of username (for extra emphasis)
        rank_num_x = left + 180
        rank_num_y = row_center_y - 38
        large_rank_font = _font(60)
        # outline
        draw.text((rank_num_x-3, rank_num_y-3), str(rank), font=large_rank_font, fill="#000000")
        draw.text((rank_num_x, rank_num_y), str(rank), font=large_rank_font, fill=RANK_COLOR)

    # Final touch: small footer text
    footer = "t.me/megagrok  •  MegaGrok Metaverse"
    fw, fh = _text_size(draw, footer, _font(28))
    draw.text(((W - fw) // 2, H - 80), footer, font=_font(28), fill="#6b6b6b")

    # Save
    canvas.convert("RGB").save(output_path)
    return output_path

# ----------------------------
# Helper functions used above
# ----------------------------
from PIL import ImageColor

def ImageColor_get_rgb(hexstr):
    # convert hex color to RGB tuple
    return ImageColor.getrgb(hexstr)

def _draw_rank_burst_custom(draw, canvas, rank, cx, cy, rank_val):
    """
    Draw a comic-style burst with rank number in center with multiple stroke layers to simulate heavy outline.
    """
    # Draw burst (slightly smaller than earlier to keep sharp)
    _draw_burst(draw, cx, cy, outer_r=86, inner_r=34, color="#FFFFFF", outline="#000000", outline_width=6, spikes=12)

    # Fill center with darker circle to host the rank
    draw.ellipse((cx-42, cy-42, cx+42, cy+42), fill="#111111", outline="#000000", width=6)

    # Rank number
    font_rank = _font(48)
    txt = str(rank_val)
    tw, th = _text_size(draw, txt, font_rank)
    tx = cx - tw/2
    ty = cy - th/2 - 2

    # heavy outline by drawing the number multiple times
    outline_offsets = [(-3,-3),(-3,3),(3,-3),(3,3),(-2,0),(2,0),(0,-2),(0,2)]
    for ox, oy in outline_offsets:
        draw.text((tx+ox, ty+oy), txt, font=font_rank, fill="#000000")
    # main fill color (white)
    draw.text((tx, ty), txt, font=font_rank, fill="#FFFFFF")

# Provide a tiny compatibility wrapper so older code referencing previous function names works
def generate_leaderboard_poster_v2(users, output_path=OUTPUT_PATH_DEFAULT):
    return generate_leaderboard_premium(users, output_path=output_path)
