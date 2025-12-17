# bot/profile_card.py
# MegaGrok Profile Card — Evolution Status Screen (WOW Edition)

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import math
import time

CANVAS_W = 1080
CANVAS_H = 1350

BG_TOP = (232, 246, 252)
BG_BOTTOM = (210, 235, 246)

CARD_RADIUS = 40

ASSET_DIR = "assets/groks"
OUT_DIR = "/tmp"
os.makedirs(OUT_DIR, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def _font(size, bold=False):
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size)
    except:
        return ImageFont.load_default()


def _vertical_gradient(draw):
    for y in range(CANVAS_H):
        ratio = y / CANVAS_H
        r = int(BG_TOP[0] * (1 - ratio) + BG_BOTTOM[0] * ratio)
        g = int(BG_TOP[1] * (1 - ratio) + BG_BOTTOM[1] * ratio)
        b = int(BG_TOP[2] * (1 - ratio) + BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (CANVAS_W, y)], fill=(r, g, b))


def _center(draw, text, y, font, fill=(0, 0, 0)):
    w = draw.textlength(text, font=font)
    draw.text(((CANVAS_W - w) / 2, y), text, font=font, fill=fill)


# -------------------------
# Main Renderer
# -------------------------
def generate_profile_card(data: dict) -> str:
    uid = data["user_id"]
    level = data.get("level", 1)
    evo = data.get("evolution", "Tadpole")

    img = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)
    _vertical_gradient(draw)

    # ---------- Title ----------
    _center(draw, f"🧬 {evo.upper()}", 40, _font(64, True), (30, 60, 80))
    _center(draw, "Evolution Stage I", 115, _font(28), (90, 120, 140))
    _center(draw, f"⚡ Level {level}", 155, _font(32, True), (40, 80, 100))

    # ---------- Aura Glow ----------
    glow = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((0, 0, 500, 500), fill=(120, 220, 160, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img.paste(glow, (290, 230), glow)

    # ---------- Grok Frame ----------
    frame_box = (260, 210, 820, 770)
    frame = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle(
        (0, 0, 560, 560),
        radius=48,
        fill=(210, 240, 225),
        outline=(140, 200, 170),
        width=6,
    )
    frame = frame.filter(ImageFilter.GaussianBlur(1))
    img.paste(frame, frame_box[:2], frame)

    # ---------- Grok Image ----------
    grok_path = os.path.join(ASSET_DIR, f"{evo.lower()}.png")
    if os.path.exists(grok_path):
        grok = Image.open(grok_path).convert("RGBA")
        grok.thumbnail((420, 420))
        gx = (CANVAS_W - grok.width) // 2
        gy = 260
        img.paste(grok, (gx, gy), grok)

    # ---------- Identity Card ----------
    panel_y = 780
    draw.rounded_rectangle(
        (140, panel_y, 940, panel_y + 140),
        radius=32,
        fill=(255, 255, 255),
    )

    name = data.get("display_name", "Unknown")
    _center(draw, f"👤 {name}", panel_y + 20, _font(32, True))
    _center(draw, f"🧬 Evolution: {evo}", panel_y + 65, _font(26))
    _center(draw, "🏆 XP Rank —", panel_y + 100, _font(22), (120, 120, 120))

    # ---------- XP Bar ----------
    cur = data.get("xp_current", 0)
    nxt = max(1, data.get("xp_to_next_level", 1))
    pct = cur / nxt

    bar_x1, bar_x2 = 220, 860
    bar_y = panel_y + 170
    draw.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + 28), 14, fill=(220, 220, 220))
    draw.rounded_rectangle(
        (bar_x1, bar_y, bar_x1 + int((bar_x2 - bar_x1) * pct), bar_y + 28),
        14,
        fill=(120, 200, 160),
    )
    _center(draw, f"{cur} / {nxt} XP", bar_y + 40, _font(22))

    _center(draw, "🌱 Growth Potential: Stable Evolution Path", bar_y + 72, _font(20), (80, 120, 100))

    # ---------- Stats ----------
    battles = data.get("wins", 0) + max(0, data.get("mobs_defeated", 0))
    draw.text((260, bar_y + 130), "⚔️ Battles Fought", font=_font(26, True), fill=(40, 60, 80))
    draw.text((260, bar_y + 165), f"{battles} Encounters", font=_font(24), fill=(60, 90, 110))

    draw.text((620, bar_y + 130), "🔥 Victory Awaits", font=_font(26, True), fill=(40, 60, 80))
    draw.text((620, bar_y + 165), "Win your first battle", font=_font(24), fill=(60, 90, 110))

    # ---------- Badges ----------
    badge_y = bar_y + 235
    _center(draw, "🔒 First Evolution  •  🔒 Hop Master  •  🔒 Battle Hardened", badge_y, _font(22), (140, 140, 140))
    _center(draw, "Unlock these by playing", badge_y + 32, _font(18), (160, 160, 160))

    # ---------- Emotional Line ----------
    _center(draw, "“Your Grok is still young… but growing.”", badge_y + 90, _font(22), (70, 100, 120))

    # ---------- Footer ----------
    _center(draw, "MEGAGROK METAVERSE", CANVAS_H - 60, _font(20), (140, 160, 170))

    out = os.path.join(OUT_DIR, f"profile_{uid}_{int(time.time())}.png")
    img.save(out)
    return out
