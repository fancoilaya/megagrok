import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# Assets directory (relative to repo root)
ASSET_DIR = "assets"

# Filenames expected in assets/
FORM_SPRITES = {
    "Tadpole": "tadpole.png",
    "Hopper": "hopper.png",
    "Ascended": "ascended.png",
}

# Fallback names if form not matched
DEFAULT_SPRITE = "tadpole.png"

# Footer text (project-level, static)
PROJECT_TG = "t.me/megagrok"
PROJECT_CA = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

# -------------------------
# Font loader (safe fallback)
# -------------------------
def load_font(path_or_size, size=None):
    """
    load_font("Roboto-Bold.ttf", 32) or load_font(size=28) fallback to default
    """
    # If called as load_font(size=28) or load_font(28)
    if size is None and isinstance(path_or_size, int):
        size = path_or_size
        path = None
    elif size is None and isinstance(path_or_size, str):
        # user passed only path string (no size) -> fallback
        path = path_or_size
        size = 24
    else:
        path = path_or_size

    try:
        if path:
            font_path = os.path.join(ASSET_DIR, path)
            return ImageFont.truetype(font_path, size)
        # try Roboto by default
        rpath = os.path.join(ASSET_DIR, "Roboto-Bold.ttf")
        return ImageFont.truetype(rpath, size)
    except Exception:
        return ImageFont.load_default()


TITLE_FONT = load_font(56)
SUBTITLE_FONT = load_font(36)
LABEL_FONT = load_font(22)
BIG_NUM_FONT = load_font(56)
BODY_FONT = load_font(20)
SMALL_FONT = load_font(16)


# -------------------------
# Utility: outlined text helper
# -------------------------
def outline_text(draw, xy, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    """
    Robust wrapper for Pillow text with stroke.
    """
    try:
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # Older Pillow versions may not support stroke_width; draw a manual outline
        x, y = xy
        oxs = [-1,0,1,-1,1,-1,0,1]
        oys = [-1,-1,-1,0,0,1,1,1]
        for ox, oy in zip(oxs, oys):
            draw.text((x+ox, y+oy), text, font=font, fill=outline, anchor=anchor)
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)


# -------------------------
# Load sprite by form/evolution
# -------------------------
def load_form_image(form_name):
    fname = FORM_SPRITES.get(form_name, DEFAULT_SPRITE)
    path = os.path.join(ASSET_DIR, fname)
    if not os.path.exists(path):
        # fallback: try default
        fallback = os.path.join(ASSET_DIR, DEFAULT_SPRITE)
        if os.path.exists(fallback):
            return Image.open(fallback).convert("RGBA")
        return None
    return Image.open(path).convert("RGBA")


# -------------------------
# Helper: draw rounded stat box
# -------------------------
def draw_stat_box(draw, bbox, label, value, fonts=None, fill_bg=(246, 193, 59), outline_color=(36, 28, 60)):
    """
    bbox: (x0,y0,x1,y1)
    label: small text above
    value: big value below
    fonts: (label_font, value_font)
    """
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle(bbox, radius=10, fill=fill_bg, outline=outline_color, width=4)
    label_font = fonts[0] if fonts and len(fonts)>0 else LABEL_FONT
    value_font = fonts[1] if fonts and len(fonts)>1 else BIG_NUM_FONT

    # label (top-left padding)
    lx = x0 + 12
    ly = y0 + 8
    outline_text(draw, (lx, ly), label.upper(), label_font, fill=(35,35,35), outline=(255,255,255), stroke=2)

    # value centered under label
    # measure using textbbox when available
    try:
        tb = draw.textbbox((0,0), value, font=value_font)
        w = tb[2] - tb[0]
        h = tb[3] - tb[1]
    except Exception:
        w, h = value_font.getsize(value)
    vx = x0 + (x1 - x0)/2 - w/2
    vy = y0 + (y1 - y0)/2 - h/2 + 8
    outline_text(draw, (vx, vy), value, value_font, fill=(20,20,20), outline=(255,255,255), stroke=3)


# -------------------------
# Main: generate_profile_image
# -------------------------
def generate_profile_image(user: dict):
    """
    Generates a 1080x1080 trading-card style profile image.

    Input `user` should be a dict that includes:
      - user_id or username (displayed top)
      - username (optional) or display_name
      - level (int)
      - form (string) -> one of Tadpole/Hopper/Ascended
      - xp_total (int)
      - wins (int)
      - rituals (int)
      - mobs_defeated (int) optional

    Fallbacks used where keys are missing.
    Returns path to saved image.
    """
    # --- safe reads from user dict ---
    username = user.get("username") or user.get("display_name") or f"@{user.get('user_id', 'player')}"
    level = int(user.get("level", user.get("lvl", 1)))
    form = user.get("form", user.get("evolution", "Tadpole"))
    xp_total = int(user.get("xp_total", user.get("xp", user.get("xp_current", 0))))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    mobs = int(user.get("mobs_defeated", user.get("mobs", 0)))

    # Canvas
    WIDTH, HEIGHT = 1080, 1080
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (246, 231, 199, 255))  # warm paper
    draw = ImageDraw.Draw(canvas)

    # Borders: heavy black outer, purple inner, yellow title bar like the reference
    border_inset = 16
    draw.rectangle([border_inset, border_inset, WIDTH-border_inset, HEIGHT-border_inset], outline=(10,10,10), width=10)
    inner_inset = 36
    inner_box = [inner_inset, inner_inset, WIDTH-inner_inset, HEIGHT-inner_inset]
    # purple frame
    draw.rectangle([inner_box[0], inner_box[1], inner_box[2], inner_box[3]], outline=(90,46,140), width=8)

    # Title yellow bar at top
    title_bar_h = 120
    title_bar = [inner_box[0], inner_box[1], inner_box[2], inner_box[1] + title_bar_h]
    draw.rectangle(title_bar, fill=(236,170,53), outline=(10,10,10), width=3)

    # "MEGAGROK" centered large
    outline_text(draw, ((WIDTH)/2, inner_box[1] + 18), "MEGAGROK", TITLE_FONT, fill=(30,30,30), outline=(5,5,5), stroke=5, anchor="ma")
    # username inside the yellow title bar UNDER the main title, centered
    outline_text(draw, ((WIDTH)/2, inner_box[1] + 64), username, SUBTITLE_FONT, fill=(30,30,30), outline=(255,255,255), stroke=3, anchor="ma")

    # Main portrait box area
    portrait_top = inner_box[1] + title_bar_h + 12
    portrait_bottom = inner_box[3] - 220  # reserve bottom area for stat boxes and footer
    portrait_bbox = (inner_box[0] + 18, portrait_top, inner_box[2] - 18, portrait_bottom)
    # draw a thin framed box
    draw.rectangle(portrait_bbox, outline=(10,10,10), width=6)

    # Background inside portrait area: subtle cosmic gradient (blue -> purple)
    try:
        bg = Image.new("RGBA", (portrait_bbox[2]-portrait_bbox[0], portrait_bbox[3]-portrait_bbox[1]), (20,20,40,255))
        bdraw = ImageDraw.Draw(bg)
        for i in range(bg.size[1]):
            # gradient
            mix = i / float(bg.size[1])
            r = int(8 + mix*20)
            g = int(18 + mix*22)
            b = int(40 + mix*50)
            bdraw.line([(0, i), (bg.size[0], i)], fill=(r,g,b,255))
        # apply slight noise/halftone by overlaying a semi-transparent dots pattern (simple approach)
        bg = bg.filter(ImageFilter.GaussianBlur(1.2))
        canvas.paste(bg, (portrait_bbox[0], portrait_bbox[1]), bg)
    except Exception:
        pass

    # Load sprite for the user's form
    sprite = load_form_image(form)
    if sprite:
        # square-crop and resize to fit nicely (about 60% of portrait height)
        pw = portrait_bbox[2] - portrait_bbox[0]
        ph = portrait_bbox[3] - portrait_bbox[1]
        # scale sprite to max ~65% of portrait height
        target_h = int(ph * 0.65)
        # preserve aspect and resize
        w, h = sprite.size
        side = min(w, h)
        # If sprite is rectangular, maintain aspect ratio centered
        sp = sprite.copy()
        # Resize keeping aspect
        ar = w / float(h)
        if h > w:
            new_w = int(target_h * (w / float(h)))
            new_h = target_h
        else:
            new_h = int(target_h / (w / float(h)))
            new_w = int(target_h * ar) if new_h > target_h else new_h
            new_h = target_h
        sp = sp.resize((int(target_h*ar), target_h)).convert("RGBA")
        sx = portrait_bbox[0] + (pw - sp.width)//2
        sy = portrait_bbox[1] + (ph - sp.height)//2
        # slight halo behind sprite
        halo = sp.copy().filter(ImageFilter.GaussianBlur(24))
        halo_tint = Image.new("RGBA", halo.size, (40,200,180,60))
        halo = Image.alpha_composite(halo, halo_tint)
        canvas.paste(halo, (sx - 10, sy - 6), halo)
        canvas.paste(sp, (sx, sy), sp)
    else:
        # fallback silhouette
        cx = (portrait_bbox[0] + portrait_bbox[2])//2
        cy = (portrait_bbox[1] + portrait_bbox[3])//2
        r = min(portrait_bbox[2]-portrait_bbox[0], portrait_bbox[3]-portrait_bbox[1])//4
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(80,80,80))
        outline_text(draw, (cx-16, cy-12), "??", BIG_NUM_FONT, fill=(255,255,255), outline=(0,0,0), stroke=3)

    # Bottom stat area (three boxes in a row): LEVEL (with evolution name), WINS, RITUALS
    bottom_top = portrait_bottom + 12
    bottom_left = inner_box[0] + 16
    bottom_right = inner_box[2] - 16
    total_w = bottom_right - bottom_left
    box_w = int((total_w - 24)/3)  # spacing 12
    box_h = 150
    spacing = 12

    # LEVEL box (left)
    level_box = (bottom_left, bottom_top, bottom_left + box_w, bottom_top + box_h)
    # evolution_name under the level number
    draw_stat_box(draw, level_box, "LEVEL", str(level), fonts=(LABEL_FONT, BIG_NUM_FONT))
    # evolution text below level number (small)
    evo_txt = str(form)
    try:
        tb = draw.textbbox((0,0), evo_txt, font=LABEL_FONT)
        w = tb[2] - tb[0]
    except Exception:
        w, _ = LABEL_FONT.getsize(evo_txt)
    ex = level_box[0] + (box_w - w)/2
    ey = level_box[1] + box_h - 36
    outline_text(draw, (ex, ey), evo_txt, LABEL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=2)

    # WINS box (center)
    wins_box = (bottom_left + box_w + spacing, bottom_top, bottom_left + box_w*2 + spacing, bottom_top + box_h)
    draw_stat_box(draw, wins_box, "WINS", str(wins), fonts=(LABEL_FONT, BIG_NUM_FONT))

    # RITUALS box (right)
    rituals_box = (bottom_left + (box_w+spacing)*2, bottom_top, bottom_right, bottom_top + box_h)
    draw_stat_box(draw, rituals_box, "RITUALS", str(rituals), fonts=(LABEL_FONT, BIG_NUM_FONT))

    # Footer strip for TG + CA (two lines centered)
    footer_h = 84
    footer_box = (inner_box[0]+6, inner_box[3]-footer_h-6, inner_box[2]-6, inner_box[3]-6)
    draw.rectangle(footer_box, fill=(246, 231, 199), outline=(10,10,10), width=2)
    # left aligned tg, right aligned ca
    padding = 22
    # TG text
    tg_text = f"TG: {PROJECT_TG}"
    ca_text = f"CA: {PROJECT_CA}"
    # TG left
    outline_text(draw, (footer_box[0] + padding, footer_box[1] + 20), tg_text, SMALL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=1)
    # CA right
    # compute width
    try:
        tb = draw.textbbox((0,0), ca_text, font=SMALL_FONT)
        w = tb[2] - tb[0]
    except Exception:
        w, _ = SMALL_FONT.getsize(ca_text)
    outline_text(draw, (footer_box[2] - padding - w, footer_box[1] + 20), ca_text, SMALL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=1)

    # Save
    out_path = f"/tmp/profile_{username.replace('@','').replace(' ','_')}.png"
    canvas.convert("RGBA").save(out_path)
    return out_path


# -------------------------
# Leaderboard: top 5 renderer
# -------------------------
def generate_leaderboard_image(rows=None):
    """
    Generates a vertical Top-5 leaderboard in the same trading-card style.

    rows: optional list of dicts:
      each dict may include:
        - rank (1..5)
        - username
        - xp (int)
        - fights (int)
        - wins (int)
        - form (optional)
    If rows is None, the caller should call get_top_users() and pass the data in.
    """
    # placeholder rows if none provided
    if rows is None:
        # example placeholders
        rows = [
            {"rank":1, "username":"FrogKing", "xp":3450, "fights":70, "wins":50, "form":"Ascended"},
            {"rank":2, "username":"HopMaster", "xp":3020, "fights":65, "wins":45, "form":"Hyper"},
            {"rank":3, "username":"TadpolePro", "xp":2800, "fights":60, "wins":40, "form":"Hopper"},
            {"rank":4, "username":"MemeRibbit", "xp":2550, "fights":55, "wins":35, "form":"Hopper"},
            {"rank":5, "username":"SwampLord", "xp":2100, "fights":50, "wins":30, "form":"Tadpole"},
        ]

    # Canvas size (vertical poster / leaderboard)
    WIDTH = 1080
    # height proportional to rows; for top5 keep a fixed poster look
    HEIGHT = 1400
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (246, 231, 199, 255))
    draw = ImageDraw.Draw(canvas)

    # Outer frames like profile style
    inset = 16
    draw.rectangle([inset, inset, WIDTH-inset, HEIGHT-inset], outline=(10,10,10), width=10)
    inner_inset = 36
    inner_box = [inner_inset, inner_inset, WIDTH-inner_inset, HEIGHT-inner_inset]
    draw.rectangle([inner_box[0], inner_box[1], inner_box[2], inner_box[3]], outline=(90,46,140), width=8)

    # Title bar
    title_bar_h = 160
    title_bar = (inner_box[0], inner_box[1], inner_box[2], inner_box[1] + title_bar_h)
    draw.rectangle(title_bar, fill=(36,56,112))
    outline_text(draw, ((WIDTH)/2, inner_box[1] + 24), "TOP 5 MEGAGROK", TITLE_FONT, fill=(236,170,53), outline=(5,5,5), stroke=5, anchor="ma")
    outline_text(draw, ((WIDTH)/2, inner_box[1] + 80), "LEADERBOARD", SUBTITLE_FONT, fill=(236,170,53), outline=(5,5,5), stroke=4, anchor="ma")

    # Row area
    row_top = title_bar[3] + 12
    row_h = 220
    row_padding = 14
    avatar_size = 128
    for i, r in enumerate(rows[:5]):
        rank = int(r.get("rank", i+1))
        uname = r.get("username", f"Player{rank}")
        xp = int(r.get("xp", 0))
        fights = int(r.get("fights", 0))
        wins = int(r.get("wins", 0))
        form = r.get("form", "Tadpole")

        y0 = row_top + i * (row_h + row_padding)
        y1 = y0 + row_h

        # row background (orange panel)
        left = inner_box[0] + 12
        right = inner_box[2] - 12
        draw.rectangle([left, y0, right, y1], fill=(236,170,53), outline=(10,10,10), width=4)

        # Rank circle left
        circle_r = 56
        cx = left + 40
        cy = y0 + row_h//2
        draw.ellipse([cx-circle_r, cy-circle_r, cx+circle_r, cy+circle_r], fill=(20,20,50), outline=(10,10,10), width=4)
        outline_text(draw, (cx, cy-14), str(rank), BIG_NUM_FONT, fill=(236,170,53), outline=(5,5,5), stroke=3, anchor="ma")

        # Avatar / sprite next to rank
        sprite = load_form_image(form)
        if sprite:
            av = sprite.copy().resize((avatar_size, avatar_size)).convert("RGBA")
            ax = cx + circle_r + 18
            ay = y0 + (row_h - avatar_size)//2
            # small halo
            halo = av.copy().filter(ImageFilter.GaussianBlur(12))
            halo_tint = Image.new("RGBA", halo.size, (40,200,180,60))
            halo = Image.alpha_composite(halo, halo_tint)
            canvas.paste(halo, (ax-8, ay-6), halo)
            canvas.paste(av, (ax, ay), av)

        # Username (large) to the right
        name_x = cx + circle_r + 18 + avatar_size + 12
        name_y = y0 + 18
        outline_text(draw, (name_x, name_y), uname, SUBTITLE_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3)

        # Stats line below username: "XP: #### • FIGHTS / WINS: FF / WW"
        stats_text = f"XP: {xp}  ·  FIGHTS / WINS: {fights} / {wins}"
        outline_text(draw, (name_x, name_y + 64), stats_text, BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)

        # small badge for top-1
        if rank == 1:
            # draw crown/flare at right edge of row
            cx_badge = right - 60
            cy_badge = y0 + 30
            # simple star burst
            draw.polygon([
                (cx_badge, cy_badge - 18),
                (cx_badge + 12, cy_badge - 6),
                (cx_badge + 30, cy_badge - 6),
                (cx_badge + 16, cy_badge + 4),
                (cx_badge + 20, cy_badge + 20),
                (cx_badge, cy_badge + 10),
                (cx_badge - 20, cy_badge + 20),
                (cx_badge - 16, cy_badge + 4),
                (cx_badge - 30, cy_badge - 6),
                (cx_badge - 12, cy_badge - 6),
            ], fill=(255,140,0), outline=(10,10,10))

    # Footer strip (TG + CA)
    footer_h = 70
    footer_box = (inner_box[0]+6, inner_box[3]-footer_h-6, inner_box[2]-6, inner_box[3]-6)
    draw.rectangle(footer_box, fill=(246, 231, 199), outline=(10,10,10), width=2)
    padding = 24
    tg_text = f"TG: {PROJECT_TG}"
    ca_text = f"CA: {PROJECT_CA}"
    outline_text(draw, (footer_box[0] + padding, footer_box[1] + 18), tg_text, SMALL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=1)
    try:
        tb = draw.textbbox((0,0), ca_text, font=SMALL_FONT)
        w = tb[2] - tb[0]
    except Exception:
        w, _ = SMALL_FONT.getsize(ca_text)
    outline_text(draw, (footer_box[2] - padding - w, footer_box[1] + 18), ca_text, SMALL_FONT, fill=(30,30,30), outline=(255,255,255), stroke=1)

    out = "/tmp/leaderboard.png"
    canvas.convert("RGBA").save(out)
    return out
