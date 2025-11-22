# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSET_DIR = "assets"
# fallback paths in case user left files in /mnt/data (where you uploaded)
FALLBACK_DIR = "/mnt/data"

PROFILE_TEMPLATE_NAMES = ["profile_base.png", "profile.png"]
LEADERBOARD_TEMPLATE_NAMES = ["leaderboard_base.png", "leaderboard.png"]

SPRITES = {
    "Tadpole": "tadpole.png",
    "Hopper": "hopper.png",
    "Ascended": "ascended.png",
}
DEFAULT_SPRITE = SPRITES["Tadpole"]

PROJECT_TG = "t.me/megagrok"
PROJECT_CA = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

# -------------------------
# Helpers: file resolution
# -------------------------
def _asset_path(filename):
    p = os.path.join(ASSET_DIR, filename)
    if os.path.exists(p):
        return p
    # check fallback /mnt/data
    fp = os.path.join(FALLBACK_DIR, filename)
    if os.path.exists(fp):
        return fp
    return p  # return the asset path anyway (will raise later)

def _find_template(possible_names):
    for n in possible_names:
        p = _asset_path(n)
        if os.path.exists(p):
            return p
    # last resort: look directly in fallback dir
    for n in possible_names:
        fp = os.path.join(FALLBACK_DIR, n)
        if os.path.exists(fp):
            return fp
    # return first asset location (will error later)
    return os.path.join(ASSET_DIR, possible_names[0])

# -------------------------
# Font loader helpers
# -------------------------
def _try_truetype(name, size):
    try:
        return ImageFont.truetype(name, size)
    except Exception:
        return None

def _load_font_by_size(size):
    # prefer Roboto-Black or Roboto-Bold in assets
    for fname in ("Roboto-Black.ttf", "Roboto-Bold.ttf", "Roboto-Bold.otf"):
        full = _asset_path(fname)
        f = _try_truetype(full, size)
        if f:
            return f
    # fallback to system default
    try:
        return ImageFont.load_default()
    except Exception:
        return None

# Outline text helper that works across pillow versions
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=4, anchor=None):
    """
    Draw text with stroke/outline. If pillow supports stroke parameters, we use them.
    Otherwise we render an 8-direction fallback outline.
    """
    try:
        draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        x,y = pos
        offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        for ox, oy in offsets:
            draw.text((x+ox, y+oy), text, font=font, fill=outline, anchor=anchor)
        draw.text(pos, text, font=font, fill=fill, anchor=anchor)

# -------------------------
# Sprite loader
# -------------------------
def _load_sprite(form_name):
    filename = SPRITES.get(form_name, DEFAULT_SPRITE)
    p = _asset_path(filename)
    if os.path.exists(p):
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            return None
    # fallback in fallback dir
    fp = os.path.join(FALLBACK_DIR, filename)
    if os.path.exists(fp):
        try:
            return Image.open(fp).convert("RGBA")
        except Exception:
            return None
    return None

# -------------------------
# Profile generator
# -------------------------
def generate_profile_image(user: dict) -> str:
    """
    Overlay-only profile generator that uses your profile_base template.

    Expected user keys:
      username (str), level (int), form (str), wins (int), rituals (int), fights (int) optional,
      xp_total (int) optional, tg (str) optional, ca (str) optional

    Returns: path to generated PNG (e.g. /tmp/profile_<username>.png)
    """
    # Resolve template
    profile_template = _find_template(PROFILE_TEMPLATE_NAMES)
    if not os.path.exists(profile_template):
        raise FileNotFoundError(f"profile template not found: checked {PROFILE_TEMPLATE_NAMES} in assets and {FALLBACK_DIR}")

    # read user data
    username = str(user.get("username") or user.get("display_name") or f"user{user.get('user_id','')}")
    level = int(user.get("level", 1))
    form = str(user.get("form", "Tadpole"))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    fights = int(user.get("fights", 0))
    xp_total = int(user.get("xp_total", 0))
    tg_line = user.get("tg", PROJECT_TG)
    ca_line = user.get("ca", PROJECT_CA)

    base = Image.open(profile_template).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # dynamic font sizes based on card width
    # (comic bold style - larger sizes)
    FONT_HUGE = _load_font_by_size(max(42, int(W * 0.075)))   # MEGAGROK
    FONT_USERNAME = _load_font_by_size(max(28, int(W * 0.04)))
    FONT_STAT_LABEL = _load_font_by_size(max(22, int(W * 0.03)))
    FONT_STAT_NUM = _load_font_by_size(max(48, int(W * 0.055)))
    FONT_FOOTER = _load_font_by_size(max(16, int(W * 0.02)))
    OUTLINE = (10, 10, 10)

    # --- Header: MEGAGROK (very large) and username beneath ---
    # place MEGAGROK centered in top title band (we pick 7% down for headline)
    headline_y = int(H * 0.055)
    outline_text(draw, (W//2, headline_y), "MEGAGROK", FONT_HUGE, fill=(30,30,30), outline=OUTLINE, stroke=8, anchor="mm")
    username_y = int(H * 0.11)
    outline_text(draw, (W//2, username_y), username.upper(), FONT_USERNAME, fill=(30,30,30), outline=OUTLINE, stroke=6, anchor="mm")

    # --- Sprite: center inside portrait box ---
    # portrait area proportion from your template (top margin -> bottom margin)
    portrait_top = int(H * 0.12)
    portrait_bottom = int(H * 0.72)
    portrait_left = int(W * 0.07)
    portrait_right = int(W * 0.93)
    portrait_w = portrait_right - portrait_left
    portrait_h = portrait_bottom - portrait_top

    sprite = _load_sprite(form)
    if sprite:
        # scale sprite to fit neatly inside the portrait area (use ~60% of portrait height)
        target_h = int(portrait_h * 0.60)
        sw, sh = sprite.size
        ar = sw / float(sh)
        new_h = target_h
        new_w = int(ar * new_h)
        if new_w > portrait_w:
            new_w = portrait_w
            new_h = int(new_w / ar)
        sprite_resized = sprite.resize((new_w, new_h), Image.LANCZOS).convert("RGBA")
        sx = portrait_left + (portrait_w - new_w)//2
        sy = portrait_top + (portrait_h - new_h)//2
        # subtle halo for pop
        halo = sprite_resized.copy().filter(ImageFilter.GaussianBlur(radius=18))
        tint = Image.new("RGBA", halo.size, (40, 200, 160, 60))
        halo = Image.alpha_composite(halo, tint)
        canvas.paste(halo, (sx-6, sy-6), halo)
        canvas.paste(sprite_resized, (sx, sy), sprite_resized)

    # --- Bottom stat boxes (three across) ---
    bottom_top = int(H * 0.73)
    side_margin = int(W * 0.06)
    total_w = W - 2*side_margin
    spacing = int(W * 0.02)
    box_w = int((total_w - spacing*2) / 3)
    box_h = int(H * 0.13)
    bx0 = side_margin
    by0 = bottom_top

    # LEVEL (left)
    level_label_pos = (bx0 + box_w//2, by0 + int(box_h * 0.18))
    outline_text(draw, level_label_pos, "LEVEL", FONT_STAT_LABEL, fill=(30,30,30), outline=OUTLINE, stroke=4, anchor="mm")
    level_num_pos = (bx0 + box_w//2, by0 + int(box_h * 0.66))
    outline_text(draw, level_num_pos, str(level), FONT_STAT_NUM, fill=(30,30,30), outline=OUTLINE, stroke=5, anchor="mm")

    # FIGHTS / WINS (center) -- bigger, show "FIGHTS / WINS" label and "FF / WW" numbers
    wins_box_x = bx0 + box_w + spacing
    wins_label_pos = (wins_box_x + box_w//2, by0 + int(box_h * 0.18))
    outline_text(draw, wins_label_pos, "FIGHTS / WINS", FONT_STAT_LABEL, fill=(30,30,30), outline=OUTLINE, stroke=4, anchor="mm")
    wins_val_pos = (wins_box_x + box_w//2, by0 + int(box_h * 0.66))
    wins_text = f"{fights} / {wins}"
    outline_text(draw, wins_val_pos, wins_text, FONT_STAT_NUM, fill=(30,30,30), outline=OUTLINE, stroke=5, anchor="mm")

    # RITUALS (right)
    rit_box_x = bx0 + 2*(box_w + spacing)
    rit_label_pos = (rit_box_x + box_w//2, by0 + int(box_h * 0.18))
    outline_text(draw, rit_label_pos, "RITUALS", FONT_STAT_LABEL, fill=(30,30,30), outline=OUTLINE, stroke=4, anchor="mm")
    rit_val_pos = (rit_box_x + box_w//2, by0 + int(box_h * 0.66))
    outline_text(draw, rit_val_pos, str(rituals), FONT_STAT_NUM, fill=(30,30,30), outline=OUTLINE, stroke=5, anchor="mm")

    # --- Footer centered: TG above CA (small & subtle) ---
    footer_y = int(H * 0.92)
    tg_pos = (W//2, footer_y - 12)
    ca_pos = (W//2, footer_y + 28)
    outline_text(draw, tg_pos, f"TG: {tg_line}", FONT_FOOTER, fill=(30,30,30), outline=(255,255,255), stroke=2, anchor="mm")
    outline_text(draw, ca_pos, f"CA: {ca_line}", FONT_FOOTER, fill=(30,30,30), outline=(255,255,255), stroke=2, anchor="mm")

    # Save
    safe = username.replace("@","").replace(" ","_")
    out_path = f"/tmp/profile_{safe}.png"
    canvas.convert("RGBA").save(out_path)
    return out_path

# -------------------------
# Leaderboard generator
# -------------------------
def generate_leaderboard_image(rows: list = None, tg: str = None, ca: str = None) -> str:
    """
    Overlay top-5 leaderboard rows on leaderboard_base template.

    rows: list of dicts: each { "rank":1, "username":"Name", "xp":1234, "fights":70, "wins":50, "form": "Hopper" }
    If rows is None, placeholder sample data used.

    Returns path to /tmp/leaderboard.png
    """
    leaderboard_template = _find_template(LEADERBOARD_TEMPLATE_NAMES)
    if not os.path.exists(leaderboard_template):
        raise FileNotFoundError(f"leaderboard template not found: checked {LEADERBOARD_TEMPLATE_NAMES}")

    if rows is None:
        rows = [
            {"rank":1, "username":"FrogKing", "xp":3450, "fights":70, "wins":50, "form":"Ascended"},
            {"rank":2, "username":"HopMaster", "xp":3020, "fights":65, "wins":45, "form":"Hopper"},
            {"rank":3, "username":"Tadpro", "xp":2800, "fights":60, "wins":40, "form":"Hopper"},
            {"rank":4, "username":"MemeRibbit", "xp":2550, "fights":55, "wins":35, "form":"Hopper"},
            {"rank":5, "username":"SwampLord", "xp":2100, "fights":50, "wins":30, "form":"Tadpole"},
        ]

    tg_line = tg or PROJECT_TG
    ca_line = ca or PROJECT_CA

    base = Image.open(leaderboard_template).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # dynamic fonts
    TITLE_FONT = _load_font_by_size(max(40, int(W * 0.065)))
    NAME_FONT = _load_font_by_size(max(30, int(W * 0.04)))
    STATS_FONT = _load_font_by_size(max(22, int(W * 0.028)))
    SMALL_F = _load_font_by_size(max(16, int(W * 0.02)))
    OUTLINE = (8,8,8)

    # header: (the template contains the header shape; we draw the text)
    outline_text(draw, (W//2, int(H * 0.07)), "TOP 5 LEADERBOARD", TITLE_FONT, fill=(236,170,53), outline=(10,10,10), stroke=6, anchor="mm")

    # Compute row positions (proportional, matching template rows)
    # header vertical space ~ 0.16 of H (from top); rows fill below that
    header_h = int(H * 0.16)
    row_top = header_h + int(H * 0.02)
    footer_h = int(H * 0.10)
    usable_h = H - row_top - footer_h
    row_h = int(usable_h / 5)
    left_margin = int(W * 0.06)
    # left column for rank circle ~ 18% width, name column uses the rest
    rank_col_w = int(W * 0.15)
    name_col_x = left_margin + rank_col_w + int(W * 0.02)

    for i, r in enumerate(rows[:5]):
        y0 = row_top + i * row_h
        name_x = name_col_x + int(W * 0.02)
        name_y = y0 + int(row_h * 0.20)
        username = str(r.get("username", f"Player{i+1}"))
        xp = int(r.get("xp", 0))
        fights = int(r.get("fights", 0))
        wins = int(r.get("wins", 0))

        outline_text(draw, (name_x, name_y), username, NAME_FONT, fill=(30,30,30), outline=(255,255,255), stroke=3, anchor="lm")
        stats_txt = f"XP: {xp}  ·  FIGHTS / WINS: {fights} / {wins}"
        outline_text(draw, (name_x, name_y + int(row_h * 0.25)), stats_txt, STATS_FONT, fill=(30,30,30), outline=(255,255,255), stroke=2, anchor="lm")

    # footer centered TG above CA (subtle)
    footer_y = H - int(H * 0.06)
    outline_text(draw, (W//2, footer_y - 18), f"TG: {tg_line}", SMALL_F, fill=(30,30,30), outline=(255,255,255), stroke=1, anchor="mm")
    outline_text(draw, (W//2, footer_y + 8), f"CA: {ca_line}", SMALL_F, fill=(30,30,30), outline=(255,255,255), stroke=1, anchor="mm")

    out = "/tmp/leaderboard.png"
    canvas.convert("RGBA").save(out)
    return out
