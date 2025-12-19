# bot/profile_card.py
# MegaGrok Profile Card — v3 Hybrid Comic × Modern Game

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import time
import random

CANVAS_W = 1080
CANVAS_H = 1350

ASSET_DIR = "assets/groks"
OUT_DIR = "/tmp"
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------
# STYLE SYSTEM (future-proof)
# ---------------------------------

EVOLUTION_STYLE = {
    "tadpole": {
        "accent": (120, 200, 160),
        "rarity": "Common",
        "stars": 1,
        "flavor": "A quiet power sleeps beneath the surface.",
    },
    "hopper": {
        "accent": (230, 160, 90),
        "rarity": "Common",
        "stars": 1,
        "flavor": "A confident stance… but greater forms await.",
    },
}

INK = (40, 60, 80)
PAPER = (238, 248, 252)


# ---------------------------------
# Helpers
# ---------------------------------

def _font(size, bold=False):
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size)
    except:
        return ImageFont.load_default()


def _center(draw, text, y, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((CANVAS_W - w) / 2, y), text, font=font, fill=fill)


def _rounded(draw, box, r, fill, outline=None, w=4):
    draw.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


# ---------------------------------
# Main Renderer
# ---------------------------------

def generate_profile_card(data: dict) -> str:
    uid = data["user_id"]
    evo = data.get("evolution", "Tadpole").lower()
    level = data.get("level", 1)

    style = EVOLUTION_STYLE.get(evo, EVOLUTION_STYLE["tadpole"])
    accent = style["accent"]

    # -------------------------------
    # Base canvas
    # -------------------------------
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), PAPER)
    draw = ImageDraw.Draw(img)

    # subtle paper noise
    noise = Image.effect_noise((CANVAS_W, CANVAS_H), 8)
    img = Image.blend(img, noise.convert("RGB"), 0.03)
    draw = ImageDraw.Draw(img)

    # -------------------------------
    # NAME BANNER (CARD IDENTITY)
    # -------------------------------
    banner_box = (140, 40, 940, 150)
    banner_shadow = Image.new("RGBA", (800, 110), (0, 0, 0, 120))
    banner_shadow = banner_shadow.filter(ImageFilter.GaussianBlur(12))
    img.paste(banner_shadow, (140, 48), banner_shadow)

    _rounded(
        draw,
        banner_box,
        28,
        fill=accent,
        outline=INK,
        w=6,
    )

    _center(draw, f"🧬 {evo.upper()}", 68, _font(60, True), (20, 40, 50))
    _center(
        draw,
        f"Evolution Stage I   {'⭐' * style['stars']} {style['rarity']}",
        122,
        _font(22),
        (30, 60, 80),
    )

    # -------------------------------
    # CORNER GLYPHS
    # -------------------------------
    _rounded(draw, (60, 200, 220, 270), 18, fill=(255, 255, 255), outline=INK, w=4)
    draw.text((85, 215), f"⚡ Lv {level}", font=_font(26, True), fill=INK)

    # -------------------------------
    # CREATURE WINDOW
    # -------------------------------
    frame_box = (240, 220, 840, 820)

    # shadow
    shadow = Image.new("RGBA", (600, 600), (0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    img.paste(shadow, (240, 240), shadow)

    # frame
    frame = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle((0, 0, 600, 600), 36, fill=(225, 245, 235), outline=INK, width=6)

    # halftone texture
    dots = Image.effect_noise((600, 600), 12)
    frame = Image.blend(frame, dots.convert("RGBA"), 0.05)

    img.paste(frame, frame_box[:2], frame)

    # glow inside frame
    glow = Image.new("RGBA", (520, 520), (*accent, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.paste(glow, (280, 280), glow)

    # grok
    grok_path = os.path.join(ASSET_DIR, f"{evo}.png")
    if os.path.exists(grok_path):
        grok = Image.open(grok_path).convert("RGBA")
        grok.thumbnail((420, 420))
        gx = (CANVAS_W - grok.width) // 2
        gy = 300
        img.paste(grok, (gx, gy), grok)

    # -------------------------------
    # IDENTITY PANEL
    # -------------------------------
    panel_y = 860
    _rounded(draw, (160, panel_y, 920, panel_y + 140), 28, fill=(255, 255, 255), outline=INK, w=4)

    name = data.get("display_name", "Unknown")
    _center(draw, f"👤 {name}", panel_y + 22, _font(34, True), INK)
    _center(draw, f"🧬 Evolution: {evo.title()}", panel_y + 70, _font(24), (60, 80, 100))
    _center(draw, "🏆 XP Rank —", panel_y + 104, _font(20), (120, 120, 120))

    # -------------------------------
    # XP TRACK
    # -------------------------------
    cur = data.get("xp_current", 0)
    nxt = max(1, data.get("xp_to_next_level", 1))
    pct = cur / nxt

    bar_y = panel_y + 180
    draw.rectangle((220, bar_y, 860, bar_y + 18), fill=(210, 210, 210))
    draw.rectangle((220, bar_y, 220 + int(640 * pct), bar_y + 18), fill=accent)

    _center(draw, f"{cur} / {nxt} XP", bar_y + 28, _font(22), INK)
    _center(draw, "🧬 Next Evolution → Level 6", bar_y + 58, _font(20), (80, 110, 130))

    # -------------------------------
    # STAT GLYPHS (ICON-FIRST)
    # -------------------------------
    battles = data.get("wins", 0) + max(0, data.get("mobs_defeated", 0))

    stats_y = bar_y + 110
    draw.text((260, stats_y), "⚔️", font=_font(36), fill=INK)
    draw.text((300, stats_y + 2), f"{battles}", font=_font(30, True), fill=INK)
    draw.text((260, stats_y + 40), "Battles", font=_font(18), fill=(80, 100, 120))

    draw.text((500, stats_y), "🔥", font=_font(36), fill=INK)
    draw.text((540, stats_y + 2), "Dormant", font=_font(24, True), fill=INK)
    draw.text((500, stats_y + 40), "Power", font=_font(18), fill=(80, 100, 120))

    draw.text((720, stats_y), "🌱", font=_font(36), fill=INK)
    draw.text((760, stats_y + 2), "Stable", font=_font(24, True), fill=INK)
    draw.text((720, stats_y + 40), "Growth", font=_font(18), fill=(80, 100, 120))

    # -------------------------------
    # MILESTONES
    # -------------------------------
    ms_y = stats_y + 90
    _center(draw, "🧬 Milestones", ms_y, _font(26, True), INK)
    _center(
        draw,
        "🔒 First Evolution (Lv 6)   •   🔒 Hop Master (7 days)   •   🔒 Battle Hardened (10 wins)",
        ms_y + 34,
        _font(18),
        (140, 140, 140),
    )

    # -------------------------------
    # FLAVOR TEXT
    # -------------------------------
    _center(
        draw,
        f"“{style['flavor']}”",
        ms_y + 86,
        _font(22),
        (70, 100, 120),
    )

    # -------------------------------
    # FOOTER
    # -------------------------------
    _center(draw, "MEGAGROK METAVERSE", CANVAS_H - 54, _font(18), (140, 160, 170))

    out = os.path.join(OUT_DIR, f"profile_{uid}_{int(time.time())}.png")
    img.save(out)
    return out
