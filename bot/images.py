# bot/images.py
# Updated image utilities for MegaGrok — includes fixed leaderboard poster generator
# Uses PIL (Pillow). Drop-in replacement for your existing images.py functions.
#
# Features:
# - Comic-style dark cosmic gradient background (option A)
# - Title in orange, usernames in cyan, yellow rank badges
# - Proper font sizing and scaling to avoid clipping
# - Outline + shadow for readability
# - Saves to persistent disk /var/data if available, otherwise /tmp
# - Returns the saved file path
#
# Usage:
#   from bot.images import generate_leaderboard_poster_v2
#   path = generate_leaderboard_poster_v2(rows)  # rows = list of dicts with username, xp_total, level...
#

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import time
from typing import List, Dict

# Config
CANVAS_W = 1080
CANVAS_H = 1920
FONT_PATHS = [
    "assets/fonts/megagrok_bold.ttf",   # preferred
    "/var/data/megagrok_bold.ttf",     # alternate persistent disk location
]
FALLBACK_FONT = None  # will use PIL default if truetype fails

# Comic palette (Option A - Dark Cosmic Gradient)
COLOR_BG_TOP = (10, 6, 20)      # near black / deep purple
COLOR_BG_BOTTOM = (24, 6, 46)   # deep indigo
COLOR_TITLE = (255, 159, 28)    # orange
COLOR_USERNAME = (110, 231, 249)  # cyan
COLOR_BADGE = (255, 209, 102)   # yellow
COLOR_XP = (255, 244, 230)      # warm white
COLOR_SHADOW = (0, 0, 0, 180)   # semi translucent black for shadows
OUTLINE_COLOR = (10, 6, 20)     # outline is dark to match comic ink

# Helper: load font with fallback
def _load_font(size: int):
    for p in FONT_PATHS:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.truetype(FALLBACK_FONT, size) if FALLBACK_FONT else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

# Helper: draw text with outline and shadow (centered)
def _draw_text_with_outline(draw: ImageDraw.Draw, xy, text, font, fill, outline_color, outline_width=3, shadow_offset=(4,4)):
    x, y = xy
    # shadow
    if shadow_offset:
        sx, sy = shadow_offset
        draw.text((x+sx, y+sy), text, font=font, fill=COLOR_SHADOW)
    # outline (draw multiple offsets)
    for ox in range(-outline_width, outline_width+1):
        for oy in range(-outline_width, outline_width+1):
            if ox == 0 and oy == 0:
                continue
            draw.text((x+ox, y+oy), text, font=font, fill=outline_color)
    # main text
    draw.text((x, y), text, font=font, fill=fill)

# Helper: draw centered text (x is center)
def _draw_centered_text(draw: ImageDraw.Draw, center_x, y, text, font, fill, outline_color, outline_width=2, shadow_offset=(3,3)):
    w, h = draw.textsize(text, font=font)
    x = center_x - w/2
    _draw_text_with_outline(draw, (x, y), text, font, fill, outline_color, outline_width, shadow_offset)

# Background gradient
def _create_cosmic_gradient(w, h, top_color, bottom_color):
    base = Image.new("RGB", (w, h), top_color)
    top = Image.new("RGB", (w, h), bottom_color)
    mask = Image.linear_gradient("L").resize((w, h))
    # linear_gradient goes black->white left->right by default in some pillow versions; rotate if needed
    grad = Image.new("RGBA", (w, h))
    for i in range(h):
        # compute blend factor top->bottom
        f = i / (h - 1)
        r = int(top_color[0] * f + bottom_color[0] * (1 - f))
        g = int(top_color[1] * f + bottom_color[1] * (1 - f))
        b = int(top_color[2] * f + bottom_color[2] * (1 - f))
        Image.Draw = ImageDraw  # no-op for style
        Image.new("RGB", (w, 1), (r, g, b)).paste(base, (0, i))
    # Simpler approach: vertical gradient by manual pixel rows
    img = Image.new("RGB", (w, h), top_color)
    px = img.load()
    for y in range(h):
        f = y / (h - 1)
        r = int(top_color[0] * (1 - f) + bottom_color[0] * f)
        g = int(top_color[1] * (1 - f) + bottom_color[1] * f)
        b = int(top_color[2] * (1 - f) + bottom_color[2] * f)
        for x in range(w):
            px[x, y] = (r, g, b)
    # Add subtle radial glow in center
    glow = Image.new("RGBA", (w, h), (0,0,0,0))
    glow_draw = ImageDraw.Draw(glow)
    max_r = int(min(w, h) * 0.6)
    cx, cy = w // 2, int(h * 0.28)
    for i in range(max_r, 0, -10):
        alpha = int(10 * (1 - (i / max_r)))
        glow_draw.ellipse((cx - i, cy - i, cx + i, cy + i), fill=(255, 80, 40, alpha))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, glow)
    return img.convert("RGB")

# Main public function
def generate_leaderboard_poster_v2(rows: List[Dict], out_path: str = None) -> str:
    """
    rows: list of dicts { "username": str, "xp_total": int, "level": int, ... }
    Returns: path to saved PNG
    """
    # Ensure at least 10 rows (fill with placeholders)
    display_rows = rows[:10]
    while len(display_rows) < 10:
        idx = len(display_rows) + 1
        display_rows.append({
            "user_id": 0,
            "username": f"User{idx}",
            "xp_total": 0,
            "level": 1
        })

    # Canvas
    canvas = _create_cosmic_gradient(CANVAS_W, CANVAS_H, COLOR_BG_TOP, COLOR_BG_BOTTOM)
    draw = ImageDraw.Draw(canvas)

    # Fonts (sizes tuned to avoid clipping)
    title_font = _load_font(110)
    rank_font = _load_font(64)
    user_font = _load_font(56)
    xp_font = _load_font(38)
    note_font = _load_font(30)

    center_x = CANVAS_W // 2

    # Title
    title_text = "MEGAGROK\nLEADERBOARD"
    # Draw big two-line title manually to control spacing
    lines = title_text.split("\n")
    cur_y = 80
    for i, line in enumerate(lines):
        f = title_font
        w, h = draw.textsize(line, font=f)
        x = center_x - w / 2
        _draw_text_with_outline(draw, (x, cur_y), line, f, COLOR_TITLE, OUTLINE_COLOR, outline_width=3, shadow_offset=(4,4))
        cur_y += h + 5

    # Subtitle / spacer
    cur_y += 40

    # Starting Y for rows
    start_y = cur_y

    # Row layout parameters
    row_h = 110
    gap = 18
    badge_radius = 42
    left_margin = 110
    right_margin = CANVAS_W - 110
    name_x = left_margin + 120  # position to the right of badge
    xp_x = right_margin - 10
    row_max = 10

    # Draw each row
    for idx, entry in enumerate(display_rows):
        row_y = start_y + idx * (row_h + gap)

        # Background subtle box for each row (slightly transparent)
        box_h = row_h
        box_w = CANVAS_W - left_margin - 100
        box_x = (CANVAS_W - box_w) // 2
        box_y = row_y - 10
        # Slight panel
        panel_color = (0, 0, 0, 60)
        panel = Image.new("RGBA", (box_w, box_h + 6), (0,0,0,0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((0, 0, box_w, box_h + 6), radius=14, fill=(0,0,0,120))
        canvas.paste(panel, (box_x, box_y), panel)

        # Rank badge (circle)
        badge_cx = box_x + 60
        badge_cy = row_y + box_h // 2
        badge_bbox = (badge_cx - badge_radius, badge_cy - badge_radius, badge_cx + badge_radius, badge_cy + badge_radius)
        # outer ring
        draw.ellipse(badge_bbox, fill=COLOR_BADGE, outline=OUTLINE_COLOR, width=4)
        # rank number
        rank_text = str(idx + 1)
        rw, rh = draw.textsize(rank_text, font=rank_font)
        draw.text((badge_cx - rw/2, badge_cy - rh/2), rank_text, font=rank_font, fill=OUTLINE_COLOR)

        # Username (cyan) with outline and shadow
        username = entry.get("username") or f"User{entry.get('user_id','?')}"
        # ensure username length not too long: truncate with ellipsis
        max_name_len = 20
        if len(username) > max_name_len:
            username = username[:max_name_len-2] + "…"

        _draw_text_with_outline(draw, (name_x, row_y + 14), username, user_font, COLOR_USERNAME, OUTLINE_COLOR, outline_width=2, shadow_offset=(3,3))

        # XP (right aligned)
        xp_text = f"{entry.get('xp_total', 0)} XP"
        xpw, xph = draw.textsize(xp_text, font=xp_font)
        xp_x_pos = xp_x - xpw
        # XP shadow for readability
        _draw_text_with_outline(draw, (xp_x_pos, row_y + 28), xp_text, xp_font, COLOR_XP, OUTLINE_COLOR, outline_width=2, shadow_offset=(3,3))

        # Level small tag under username
        level_text = f"LV {entry.get('level',1)}"
        draw.text((name_x, row_y + 68), level_text, font=note_font, fill=(220,200,120))

    # Footer small note
    foot = "t.me/megagrok"
    fw, fh = draw.textsize(foot, font=note_font)
    _draw_text_with_outline(draw, (center_x - fw/2, CANVAS_H - 110), foot, note_font, (200,180,130), OUTLINE_COLOR, outline_width=2, shadow_offset=(2,2))

    # Save file
    if out_path is None:
        # try persistent disk first
        try_paths = ["/var/data", "/tmp"]
        out_path = None
        for p in try_paths:
            try:
                if os.path.isdir(p) and os.access(p, os.W_OK):
                    fn = f"leaderboard_v2_{int(time.time())}.png"
                    out_path = os.path.join(p, fn)
                    break
            except:
                continue
        if out_path is None:
            # fallback to current dir
            out_path = f"leaderboard_v2_{int(time.time())}.png"

    # Ensure directory exists
    out_dir = os.path.dirname(out_path)
    if out_dir and not os.path.exists(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except:
            pass

    canvas.save(out_path, format="PNG", optimize=True)
    return out_path


# If you want to test locally:
if __name__ == "__main__":
    # quick test: create fake rows
    test_rows = []
    for i in range(1, 8):
        test_rows.append({"user_id": 1000+i, "username": f"User{i}", "xp_total": i*123, "level": i+1})
    p = generate_leaderboard_poster_v2(test_rows)
    print("Saved:", p)
