# bot/images.py
# MegaGrok Leaderboard Renderer — Comic Style Premium Edition (improved)
import os
import math
import textwrap
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "assets/fonts/megagrok.ttf"
DEFAULT_FONT = "DejaVuSans-Bold.ttf"

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.truetype(DEFAULT_FONT, size)

# measure text bounding box width/height reliably
def measure(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return (box[2] - box[0], box[3] - box[1])

def draw_text_outline(draw, xy, text, font, fill, outline="black", width=3):
    x, y = xy
    # draw thin outline first
    for dx in range(-width, width+1):
        for dy in range(-width, width+1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)

def draw_medal(draw, x, y, rank):
    if rank == 1:
        color = "#FFD700"  # Gold
    elif rank == 2:
        color = "#C0C0C0"  # Silver
    elif rank == 3:
        color = "#CD7F32"  # Bronze
    else:
        return

    r = 32
    cx, cy = x + r, y + r
    pts = []
    spikes = 18
    for i in range(spikes):
        angle = i * math.tau / spikes
        dist = r if i % 2 == 0 else r * 0.55
        pts.append((cx + dist * math.cos(angle), cy + dist * math.sin(angle)))

    draw.polygon(pts, fill=color, outline="black")
    draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill="white", outline="black")

    fnt = load_font(28)
    txt = str(rank)
    tw, th = measure(draw, txt, fnt)
    draw.text((cx - tw/2, cy - th/2), txt, font=fnt, fill="black")

def _safe_username_from_user(user):
    # Accept different key names, prefer human username (without '@'), else fallback to "User<ID>"
    uname = None
    for key in ("username", "user_name", "name", "display_name"):
        if user.get(key):
            uname = str(user.get(key))
            break
    if not uname:
        uid = user.get("user_id") or user.get("id")
        return f"User{uid}"
    # strip leading @
    uname = uname.lstrip("@")
    return uname

def _wrap_name_for_width(draw, name, font, max_w):
    if not name:
        return ""
    # If it fits, return as single line.
    w, h = measure(draw, name, font)
    if w <= max_w:
        return [name]
    # otherwise attempt to wrap into 2 lines
    wrapper = textwrap.TextWrapper(width=20)
    # greedy fallback: split by spaces into two roughly equal parts
    parts = name.split()
    if len(parts) <= 1:
        # just truncate
        return [name[:max(0, int(max_w / (font.size*0.6)))] + "…"]
    # try to split in the middle
    mid = len(parts) // 2
    a = " ".join(parts[:mid])
    b = " ".join(parts[mid:])
    # if still too long per line, further wrap
    lines = []
    for seg in (a, b):
        seg = seg.strip()
        if not seg:
            continue
        seg_w, _ = measure(draw, seg, font)
        if seg_w <= max_w:
            lines.append(seg)
        else:
            # fallback wrap with textwrap (approx)
            wrapped = wrapper.wrap(seg)
            for line in wrapped:
                if measure(draw, line, font)[0] <= max_w or len(lines) >= 2:
                    lines.append(line)
                else:
                    # trim forcibly
                    trimmed = line[: max(1, int(max_w / (font.size * 0.6)))] + "…"
                    lines.append(trimmed)
            # keep max 2 lines
    return lines[:2]

def generate_leaderboard_premium(users):
    """
    users: list of dicts with keys: user_id, username (optional), level, xp_total
    """
    W, H = 1080, 1920
    bg_color = (24, 24, 26)
    img = Image.new("RGB", (W, H), bg_color)
    dr = ImageDraw.Draw(img)

    # Title (allow two lines)
    title = "MEGAGROK LEADERBOARD"
    title_font = load_font(92)
    # try splitting title into two lines if too wide
    tw, th = measure(dr, title, title_font)
    if tw > W - 120:
        # split after first word or into two reasonable chunks
        parts = title.split()
        mid = len(parts) // 2
        t1 = " ".join(parts[:mid])
        t2 = " ".join(parts[mid:])
        title_lines = [t1, t2]
    else:
        title_lines = [title]

    # draw title lines centered
    y = 60
    for line in title_lines:
        f = title_font
        w, h = measure(dr, line, f)
        draw_text_outline(dr, ((W - w) // 2, y), line, f, fill="#FFB545", outline="black", width=3)
        y += h + 6
    # header separator
    sep_y = y + 10
    dr.line((80, sep_y, W - 80, sep_y), fill=(60, 60, 60), width=4)

    # Row layout
    start_y = sep_y + 24
    # dynamic row height based on fonts
    name_font = load_font(54)
    xp_font = load_font(36)
    rank_font = load_font(42)

    row_padding = 24
    row_h = 110  # base; we'll use more if name wraps

    max_name_width = W - 420  # leave space for medal/rank and margins

    for idx, user in enumerate(users[:12]):
        rank = idx + 1
        y = start_y + idx * (row_h + 18)

        # derive display fields robustly
        username = _safe_username_from_user(user)
        level = user.get("level", user.get("lvl", 1)) or 1
        xp = user.get("xp_total", user.get("xp", 0)) or 0

        # Medal or rank
        medal_x = 120
        if rank <= 3:
            draw_medal(dr, medal_x, y + 6, rank)
            name_x = medal_x + 120
        else:
            rank_text = f"{rank}."
            draw_text_outline(dr, (medal_x, y + 18), rank_text, rank_font, fill="white", outline="black", width=2)
            name_x = medal_x + 120

        # Wrap/truncate username to at most 2 lines
        name_lines = _wrap_name_for_width(dr, username, name_font, max_name_width)
        # draw username lines stacked
        line_y = y + 6
        for i, nl in enumerate(name_lines):
            draw_text_outline(dr, (name_x, line_y), nl, name_font, fill="#7EF2FF", outline="black", width=3)
            nh = measure(dr, nl, name_font)[1]
            line_y += nh + 6

        # Stats: level + xp placed on separate line (right aligned)
        stats_text = f"LV {level}  •  {xp} XP"
        st_w, st_h = measure(dr, stats_text, xp_font)
        stats_x = W - 120 - st_w
        # vertical position: align stats with second line if exists, else with first
        if len(name_lines) >= 2:
            stats_y = y + 6 + measure(dr, name_lines[0], name_font)[1] + 6
        else:
            stats_y = y + 6 + measure(dr, name_lines[0], name_font)[1] // 2

        draw_text_outline(dr, (stats_x, stats_y), stats_text, xp_font, fill="#FFB545", outline="black", width=2)

        # Row background subtle rectangle for better contrast
        rect_top = y - 6
        rect_bottom = y + row_h + 6
        rect_color = (40, 40, 40)
        dr.rounded_rectangle((80, rect_top, W - 80, rect_top + row_h), radius=12, fill=rect_color)

        # redraw medal/rank and texts above the rectangle to ensure visibility
        if rank <= 3:
            draw_medal(dr, medal_x, y + 6, rank)
        else:
            draw_text_outline(dr, (medal_x, y + 18), f"{rank}.", rank_font, fill="white", outline="black", width=2)
        # re-draw username lines (on top of rect)
        line_y = y + 6
        for nl in name_lines:
            draw_text_outline(dr, (name_x, line_y), nl, name_font, fill="#7EF2FF", outline="black", width=3)
            line_y += measure(dr, nl, name_font)[1] + 6
        # re-draw stats
        draw_text_outline(dr, (stats_x, stats_y), stats_text, xp_font, fill="#FFB545", outline="black", width=2)

    # Footer
    footer = "MegaGrok Metaverse"
    ff = load_font(36)
    fw, fh = measure(dr, footer, ff)
    draw_text_outline(dr, ((W - fw) // 2, H - 110), footer, ff, fill="#777777", outline="black", width=2)

    out = "/tmp/leaderboard.jpg"
    img.save(out, quality=90)
    return out
