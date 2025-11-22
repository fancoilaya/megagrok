# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSET_DIR = "assets"
PROFILE_TEMPLATE = os.path.join(ASSET_DIR, "profile_base.png")
LEADERBOARD_TEMPLATE = os.path.join(ASSET_DIR, "leaderboard_base.png")

SPRITES = {
    "Tadpole": os.path.join(ASSET_DIR, "tadpole.png"),
    "Hopper": os.path.join(ASSET_DIR, "hopper.png"),
    "Ascended": os.path.join(ASSET_DIR, "ascended.png"),
}
DEFAULT_SPRITE = SPRITES.get("Tadpole")

PROJECT_TG = "t.me/megagrok"
PROJECT_CA = "FZL2K9TBybDh32KfJWQBhMtQ71PExyNXiry8Y5e2pump"

# -------------------------
# Font loader
# -------------------------
def _load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = _load_font(56)
SUBTITLE_FONT = _load_font(36)
LABEL_FONT = _load_font(22)
BIG_NUM_FONT = _load_font(64)
BODY_FONT = _load_font(28)
SMALL_FONT = _load_font(18)

# -------------------------
# Outline text helper
# -------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=3, anchor=None):
    try:
        draw.text(pos, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline, anchor=anchor)
    except TypeError:
        # fallback for Pillow versions without stroke support
        x,y = pos
        for ox, oy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            draw.text((x+ox, y+oy), text, font=font, fill=outline, anchor=anchor)
        draw.text(pos, text, font=font, fill=fill, anchor=anchor)

# -------------------------
# Sprite loader
# -------------------------
def load_sprite(form_name):
    path = SPRITES.get(form_name, DEFAULT_SPRITE)
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            return None
    return None

# -------------------------
# Internal helpers to compute positions by template size (proportional)
# -------------------------
def _pct(value, total):
    return int(value * total)

def _centered_x_for_text(draw, text, font, canvas_width):
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        w = bbox[2] - bbox[0]
    except Exception:
        w, _ = font.getsize(text)
    return (canvas_width - w) // 2

# -------------------------
# Profile renderer (pixel-perfect relative placement)
# -------------------------
def generate_profile_image(user: dict) -> str:
    """
    user keys:
      username, level, form, xp_total, wins, rituals, tg (optional), ca (optional)
    """
    if not os.path.exists(PROFILE_TEMPLATE):
        raise FileNotFoundError(f"Profile template not found at {PROFILE_TEMPLATE}")

    username = user.get("username") or user.get("display_name") or f"user{user.get('user_id','')}"
    level = int(user.get("level", 1))
    form = user.get("form", "Tadpole")
    xp_total = int(user.get("xp_total", 0))
    wins = int(user.get("wins", 0))
    rituals = int(user.get("rituals", 0))
    tg_line = user.get("tg", PROJECT_TG)
    ca_line = user.get("ca", PROJECT_CA)

    base = Image.open(PROFILE_TEMPLATE).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # --- Text placements derived from the template proportions ---
    # Title bar center: username
    # These proportions were tuned to the template you uploaded.
    username_y = int(H * 0.065)  # vertical center for username band
    outline_text(draw, (W//2, username_y), username, SUBTITLE_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="mm")

    # Portrait area: we'll paste the sprite centered in the big portrait box
    portrait_top = int(H * 0.12)
    portrait_bottom = int(H * 0.72)
    portrait_left = int(W * 0.07)
    portrait_right = int(W * 0.93)
    portrait_w = portrait_right - portrait_left
    portrait_h = portrait_bottom - portrait_top

    sprite = load_sprite(form)
    if sprite:
        # scale sprite to ~60% of portrait height, keep aspect
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
        # halo for polish (very subtle)
        halo = sprite_resized.copy().filter(ImageFilter.GaussianBlur(radius=16))
        halo_tint = Image.new("RGBA", halo.size, (40,200,160,48))
        halo = Image.alpha_composite(halo, halo_tint)
        canvas.paste(halo, (sx-6, sy-6), halo)
        canvas.paste(sprite_resized, (sx, sy), sprite_resized)

    # --- Stat boxes positions (three boxes across bottom of portrait area) ---
    bottom_top = int(H * 0.73)
    side_margin = int(W * 0.06)
    total_w = W - side_margin*2
    spacing = int(W * 0.02)
    box_w = int((total_w - spacing*2) / 3)
    box_h = int(H * 0.13)
    bx0 = side_margin
    by0 = bottom_top

    # Level (left)
    lvl_x = bx0 + 16
    lvl_label_y = by0 + 12
    outline_text(draw, (lvl_x, lvl_label_y), "LEVEL", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    # big level centered in box
    lvl_val_x = bx0 + box_w//2
    lvl_val_y = by0 + box_h//2 - 8
    outline_text(draw, (lvl_val_x, lvl_val_y), str(level), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="mm")
    # evolution name below
    evo_y = by0 + box_h - 28
    outline_text(draw, (bx0 + box_w//2, evo_y), str(form), LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="mm")

    # Wins (center)
    wins_box_x = bx0 + box_w + spacing
    outline_text(draw, (wins_box_x + 16, lvl_label_y), "WINS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    outline_text(draw, (wins_box_x + box_w//2, lvl_val_y), str(wins), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="mm")

    # Rituals (right)
    rit_box_x = bx0 + 2*(box_w + spacing)
    outline_text(draw, (rit_box_x + 16, lvl_label_y), "RITUALS", LABEL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")
    outline_text(draw, (rit_box_x + box_w//2, lvl_val_y), str(rituals), BIG_NUM_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="mm")

    # Footer strip TG (left) + CA (right)
    footer_y = int(H * 0.92)
    padding = int(W * 0.06)
    outline_text(draw, (padding, footer_y), f"TG: {tg_line}", SMALL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")
    ca_txt = f"CA: {ca_line}"
    try:
        tb = draw.textbbox((0,0), ca_txt, font=SMALL_FONT)
        cw = tb[2] - tb[0]
    except Exception:
        cw, _ = SMALL_FONT.getsize(ca_txt)
    outline_text(draw, (W - padding - cw, footer_y), ca_txt, SMALL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")

    safe = str(username).replace("@", "").replace(" ", "_")
    out = f"/tmp/profile_{safe}.png"
    canvas.convert("RGBA").save(out)
    return out

# -------------------------
# Leaderboard overlay renderer
# -------------------------
def generate_leaderboard_image(rows=None, tg=None, ca=None) -> str:
    """
    rows: list(dict) with keys username, xp, fights, wins, form (optional), rank (optional)
    If rows is None, placeholder data will be used.
    """
    if not os.path.exists(LEADERBOARD_TEMPLATE):
        raise FileNotFoundError(f"Leaderboard template not found at {LEADERBOARD_TEMPLATE}")

    if rows is None:
        rows = [
            {"rank":1, "username":"FrogKing", "xp":3450, "fights":70, "wins":50, "form":"Ascended"},
            {"rank":2, "username":"HopMaster", "xp":3020, "fights":65, "wins":45, "form":"Hopper"},
            {"rank":3, "username":"TadpolePro", "xp":2800, "fights":60, "wins":40, "form":"Hopper"},
            {"rank":4, "username":"MemeRibbit", "xp":2550, "fights":55, "wins":35, "form":"Hopper"},
            {"rank":5, "username":"SwampLord", "xp":2100, "fights":50, "wins":30, "form":"Tadpole"},
        ]

    base = Image.open(LEADERBOARD_TEMPLATE).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)

    # header
    outline_text(draw, (W//2, int(H * 0.06)), "TOP 5 LEADERBOARD", TITLE_FONT, fill=(236,170,53), outline=(5,5,5), stroke=5, anchor="mm")

    # compute row positions using proportions that match the template
    title_bar_h = int(H * 0.16)
    row_top = title_bar_h + int(H * 0.03)
    footer_area = int(H * 0.12)
    available_h = H - row_top - footer_area
    row_h = int(available_h / 5)
    left_margin = int(W * 0.05)
    avatar_x = left_margin + int(W * 0.06)

    for i, r in enumerate(rows[:5]):
        rank = int(r.get("rank", i+1))
        username = r.get("username", f"Player{rank}")
        xp = int(r.get("xp", 0))
        fights = int(r.get("fights", 0))
        wins = int(r.get("wins", 0))
        form = r.get("form", "Tadpole")

        y0 = row_top + i * (row_h + int(H * 0.01))
        name_x = avatar_x + int(row_h * 0.6) + 18
        name_y = y0 + int(row_h * 0.12)
        outline_text(draw, (name_x, name_y), username, SUBTITLE_FONT, fill=(20,20,20), outline=(255,255,255), stroke=3, anchor="lm")

        stats_text = f"XP: {xp}  ·  FIGHTS / WINS: {fights} / {wins}"
        outline_text(draw, (name_x, name_y + 56), stats_text, BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2, anchor="lm")

        # (optional) add sprite where frog used to be in template; coordinates left of name_x
        # sprite = load_sprite(form)
        # if sprite:
        #     av_h = int(row_h * 0.6)
        #     av = sprite.resize((av_h, av_h), Image.LANCZOS).convert("RGBA")
        #     ax = avatar_x
        #     ay = y0 + (row_h - av_h)//2
        #     canvas.paste(av, (ax, ay), av)

    # footer
    tg_line = tg or PROJECT_TG
    ca_line = ca or PROJECT_CA
    footer_y = H - int(H * 0.08)
    padding = int(W * 0.05)
    outline_text(draw, (padding, footer_y), f"TG: {tg_line}", SMALL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")
    ca_txt = f"CA: {ca_line}"
    try:
        tb = draw.textbbox((0,0), ca_txt, font=SMALL_FONT)
        cw = tb[2] - tb[0]
    except Exception:
        cw, _ = SMALL_FONT.getsize(ca_txt)
    outline_text(draw, (W - padding - cw, footer_y), ca_txt, SMALL_FONT, fill=(20,20,20), outline=(255,255,255), stroke=1, anchor="lm")

    out = "/tmp/leaderboard.png"
    canvas.convert("RGBA").save(out)
    return out
