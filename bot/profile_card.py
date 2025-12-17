# bot/profile_card.py
# MegaGrok Profile Card — Evolution Status Screen v2.1

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import time

CANVAS_W = 1080
CANVAS_H = 1350

BG_TOP = (232, 246, 252)
BG_BOTTOM = (206, 232, 244)

ASSET_DIR = "assets/groks"
OUT_DIR = "/tmp"
os.makedirs(OUT_DIR, exist_ok=True)

# Evolution accent colors (future-proof)
EVOLUTION_COLORS = {
    "tadpole": (120, 200, 160),
}

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
        t = y / CANVAS_H
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        draw.line([(0, y), (CANVAS_W, y)], fill=(r, g, b))


def _center(draw, text, y, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((CANVAS_W - w) / 2, y), text, font=font, fill=fill)


# -------------------------
# Main Renderer
# -------------------------
def generate_profile_card(data: dict) -> str:
    uid = data["user_id"]
    level = data.get("level", 1)
    evo = data.get("evolution", "Tadpole")
    evo_key = evo.lower()

    accent = EVOLUTION_COLORS.get(evo_key, (120, 200, 160))

    img = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)
    _vertical_gradient(draw)

    # ---------- Header ----------
    _center(draw, f"🧬 {evo.upper()}", 40, _font(64, True), (30, 60, 80))
    _center(draw, "Evolution Stage I", 115, _font(28), (90, 120, 140))
    _center(draw, f"⚡ Level {level}", 155, _font(32, True), (40, 80, 100))
    _center(draw, "⚡ Power: Dormant", 195, _font(22), (80, 110, 130))

    # ---------- Aura Glow ----------
    glow = Image.new("RGBA", (520, 520), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((0, 0, 520, 520), fill=(*accent, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img.paste(glow, (280, 235), glow)

    # ---------- Frame Shadow ----------
    shadow = Image.new("RGBA", (580, 580), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((0, 0, 580, 580), 56, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.paste(shadow, (250, 255), shadow)

    # ---------- Frame ----------
    frame = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle(
        (0, 0, 560, 560),
        radius=48,
        fill=(210, 245, 230),
        outline=accent,
        width=6,
    )
    img.paste(frame, (260, 260), frame)

    # ---------- Grok ----------
    grok_path = os.path.join(ASSET_DIR, f"{evo_key}.png")
    if os.path.exists(grok_path):
        grok = Image.open(grok_path).convert("RGBA")
        grok.thumbnail((420, 420))
        gx = (CANVAS_W - grok.width) // 2
        gy = 310
        img.paste(grok, (gx, gy), grok)

    # ---------- Identity Card ----------
    panel_y = 830
    panel = Image.new("RGBA", (820, 170), (255, 255, 255, 255))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((0, 0, 820, 170), 36, fill=(255, 255, 255))
    panel_shadow = panel.filter(ImageFilter.GaussianBlur(10))
    img.paste(panel_shadow, (130, panel_y + 8), panel_shadow)
    img.paste(panel, (130, panel_y), panel)

    name = data.get("display_name", "Unknown")
    _center(draw, f"👤 {name}", panel_y + 22, _font(34, True), (20, 40, 60))
    _center(draw, f"🧬 Evolution: {evo}", panel_y + 68, _font(26), (60, 80, 100))
    _center(draw, "🏆 XP Rank —", panel_y + 108, _font(22), (130, 130, 130))

    # ---------- XP Bar ----------
    cur = data.get("xp_current", 0)
    nxt = max(1, data.get("xp_to_next_level", 1))
    pct = cur / nxt

    bar_x1, bar_x2 = 240, 840
    bar_y = panel_y + 200

    draw.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + 30), 15, fill=(220, 220, 220))
    draw.rounded_rectangle(
        (bar_x1, bar_y, bar_x1 + int((bar_x2 - bar_x1) * pct), bar_y + 30),
        15,
        fill=accent,
    )

    _center(draw, f"{cur} / {nxt} XP", bar_y + 44, _font(22), (40, 70, 90))
    _center(draw, "🌱 Growth Potential: Stable Evolution Path", bar_y + 78, _font(20), (70, 110, 100))
    _center(draw, "🧬 Next Evolution at Level 5", bar_y + 108, _font(20), (90, 120, 140))

    # ---------- Stats ----------
    battles = data.get("wins", 0) + max(0, data.get("mobs_defeated", 0))

    draw.text((270, bar_y + 150), "⚔️ Battles Fought", font=_font(26, True), fill=(30, 60, 80))
    draw.text((270, bar_y + 185), f"{battles} Encounters", font=_font(24), fill=(60, 90, 110))

    draw.text((610, bar_y + 150), "🔥 Victory Awaits", font=_font(26, True), fill=(30, 60, 80))
    draw.text((610, bar_y + 185), "Win your first battle", font=_font(24), fill=(60, 90, 110))

    # ---------- Milestones ----------
    ms_y = bar_y + 245
    _center(draw, "🧬 Milestones", ms_y, _font(26, True), (50, 80, 100))
    _center(
        draw,
        "🔒 First Evolution (Lv 5)   •   🔒 Hop Master (7 days)   •   🔒 Battle Hardened (10 wins)",
        ms_y + 36,
        _font(20),
        (140, 140, 140),
    )

    # ---------- Lore ----------
    _center(
        draw,
        "“The Tadpole stirs… sensing greater forms ahead.”",
        ms_y + 90,
        _font(22),
        (70, 100, 120),
    )

    # ---------- Footer ----------
    _center(draw, "MEGAGROK METAVERSE", CANVAS_H - 60, _font(20), (140, 160, 170))

    out = os.path.join(OUT_DIR, f"profile_{uid}_{int(time.time())}.png")
    img.save(out)
    return out
