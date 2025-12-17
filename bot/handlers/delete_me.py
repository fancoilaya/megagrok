# bot/profile_card.py
# MegaGrok Profile Card — Clean, Colorful, Playful (Style A)

from PIL import Image, ImageDraw, ImageFont
import os
import math

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

CANVAS_W = 1080
CANVAS_H = 1350

GROK_ASSET_PATH = "assets/groks"

BACKGROUND_TOP = (235, 248, 255)
BACKGROUND_BOTTOM = (210, 235, 255)

CARD_RADIUS = 40

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Evolution → image mapping (explicit & safe)
EVOLUTION_IMAGES = {
    "Tadpole": "tadpole.png",
    "Hopper": "hopper.png",
    "Elder": "elder.png",
}

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def _load_font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_PATH, size)
    except:
        return ImageFont.load_default()

def _vertical_gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        ratio = y / h
        r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return base

def _rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

# -------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------

def generate_profile_card(data: dict) -> str:
    """
    Generates a profile card image and returns the file path.
    """

    uid = data.get("user_id")
    name = data.get("display_name", "Unknown")
    level = data.get("level", 1)
    xp_cur = data.get("xp_current", 0)
    xp_next = data.get("xp_to_next_level", 100)
    xp_total = data.get("xp_total", 0)
    wins = data.get("wins", 0)
    battles = data.get("mobs_defeated", wins)
    evo_name = data.get("evolution", "Tadpole")
    growth_rate = int((data.get("evolution_multiplier", 1.0) - 1) * 100)

    losses = max(0, battles - wins)
    win_rate = int((wins / battles) * 100) if battles > 0 else 0

    # -------------------------------------------------
    # CANVAS
    # -------------------------------------------------

    img = _vertical_gradient(CANVAS_W, CANVAS_H, BACKGROUND_TOP, BACKGROUND_BOTTOM)
    draw = ImageDraw.Draw(img)

    # -------------------------------------------------
    # HERO — GROK IMAGE
    # -------------------------------------------------

    grok_file = EVOLUTION_IMAGES.get(evo_name, "tadpole.png")
    grok_path = os.path.join(GROK_ASSET_PATH, grok_file)

    try:
        grok = Image.open(grok_path).convert("RGBA")
        grok.thumbnail((700, 450), Image.LANCZOS)
        gx = (CANVAS_W - grok.width) // 2
        gy = 80
        img.paste(grok, (gx, gy), grok)
    except Exception:
        pass

    # Fonts
    f_title = _load_font(64, bold=True)
    f_sub = _load_font(36, bold=True)
    f_text = _load_font(30)
    f_small = _load_font(26)

    # -------------------------------------------------
    # TITLE
    # -------------------------------------------------

    draw.text((CANVAS_W // 2, 30), evo_name.upper(), fill=(40, 60, 90),
              font=f_title, anchor="mm")
    draw.text((CANVAS_W // 2, 100), f"LEVEL {level}", fill=(60, 90, 120),
              font=f_sub, anchor="mm")

    # -------------------------------------------------
    # INFO CARD
    # -------------------------------------------------

    card_y = 560
    _rounded_rect(draw, (140, card_y, 940, card_y + 160), CARD_RADIUS, fill=(255, 255, 255))

    draw.text((180, card_y + 25), f"👤 {name}", fill=(0, 0, 0), font=f_text)
    draw.text((180, card_y + 70), f"🧬 Evolution: {evo_name}", fill=(60, 60, 60), font=f_small)
    draw.text((180, card_y + 110), "🏆 XP Rank: —", fill=(60, 60, 60), font=f_small)

    # -------------------------------------------------
    # XP BAR
    # -------------------------------------------------

    bar_x1 = 180
    bar_x2 = 900
    bar_y = card_y + 200
    bar_h = 26

    draw.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + bar_h),
                           radius=13, fill=(220, 220, 220))

    pct = min(1.0, xp_cur / xp_next if xp_next > 0 else 0)
    fill_w = int((bar_x2 - bar_x1) * pct)

    draw.rounded_rectangle((bar_x1, bar_y, bar_x1 + fill_w, bar_y + bar_h),
                           radius=13, fill=(90, 200, 140))

    draw.text((CANVAS_W // 2, bar_y - 34),
              f"{xp_cur} / {xp_next} XP",
              fill=(0, 0, 0),
              font=f_small,
              anchor="mm")

    draw.text((CANVAS_W // 2, bar_y + 36),
              f"Growth Rate +{growth_rate}%",
              fill=(80, 120, 90),
              font=f_small,
              anchor="mm")

    # -------------------------------------------------
    # PvE STATS
    # -------------------------------------------------

    stats_y = bar_y + 90
    draw.text((300, stats_y), "⚔️ Battles", fill=(0, 0, 0), font=f_text, anchor="mm")
    draw.text((300, stats_y + 45), f"{wins}W / {losses}L", fill=(60, 60, 60), font=f_small, anchor="mm")

    draw.text((780, stats_y), "🔥 Win Rate", fill=(0, 0, 0), font=f_text, anchor="mm")
    draw.text((780, stats_y + 45), f"{win_rate}%", fill=(60, 60, 60), font=f_small, anchor="mm")

    # -------------------------------------------------
    # BADGES (STATIC V1)
    # -------------------------------------------------

    badge_y = stats_y + 120
    badges = ["🏅 First Evolution", "🏅 Hop Master", "🏅 Battle Hardened"]

    bx = 200
    for b in badges:
        draw.text((bx, badge_y), b, fill=(80, 80, 120), font=f_small)
        bx += 260

    # -------------------------------------------------
    # FOOTER
    # -------------------------------------------------

    draw.text((CANVAS_W // 2, CANVAS_H - 40),
              "MEGAGROK METAVERSE",
              fill=(120, 140, 170),
              font=f_small,
              anchor="mm")

    # -------------------------------------------------
    # SAVE
    # -------------------------------------------------

    out_path = f"/tmp/megagrok_profile_{uid}.png"
    img.save(out_path, "PNG")
    return out_path
