# bot/images.py
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from bot.db import get_top_users

ASSET_DIR = "assets"

# -------------------------
# Font loader
# -------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()

TITLE_FONT = load_font(56)
SUBTITLE_FONT = load_font(32)
BODY_FONT = load_font(22)
SMALL_FONT = load_font(16)
BIG_FONT = load_font(40)


# -------------------------
# Utility: outline text (works across Pillow versions)
# -------------------------
def outline_text(draw, xy, text, font, fill=(255,255,255), outline=(0,0,0), stroke=4):
    """
    Draw text with an outline by using stroke parameters.
    """
    # Pillow supports stroke parameters; fallback if not present is unlikely but tolerated
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=outline)


# -------------------------
# Sprite loader (unchanged)
# -------------------------
def load_form_image(form_name):
    form_map = {
        "Tadpole": "tadpole.png",
        "Hopper": "hopper.png",
        "Ascended": "ascended.png",
        "Ascended Hopper": "ascended.png",
    }
    filename = form_map.get(form_name, "tadpole.png")
    path = os.path.join(ASSET_DIR, filename)
    if not os.path.exists(path):
        return None
    return Image.open(path).convert("RGBA")


# -------------------------
# Small helpers for drawing
# -------------------------
def draw_rounded_bar(base_img, bbox, pct, radius=12, bg_color="#2b2b2b", fill_color="#ffca28", outline_color="#000000"):
    draw = ImageDraw.Draw(base_img)
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle(bbox, radius=radius, fill=bg_color)
    width = x1 - x0
    fill_w = int(width * max(0.0, min(pct, 1.0)))
    if fill_w > 0:
        fill_box = (x0, y0, x0 + fill_w, y1)
        draw.rounded_rectangle(fill_box, radius=radius, fill=fill_color)
    if outline_color:
        draw.rounded_rectangle(bbox, radius=radius, outline=outline_color, width=2)


def draw_xp_ring(size, center, radius, thickness, pct, bg=(34,34,34,200), fg=(255,200,40,230)):
    # similar to earlier ring but with different default colors
    layer = Image.new("RGBA", size, (0,0,0,0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    outer = [cx-radius, cy-radius, cx+radius, cy+radius]
    inner = [cx-(radius-thickness), cy-(radius-thickness), cx+(radius-thickness), cy+(radius-thickness)]

    # mask for ring
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(outer, fill=255)
    md.ellipse(inner, fill=0)

    bg_layer = Image.new("RGBA", size, (0,0,0,0))
    bdraw = ImageDraw.Draw(bg_layer)
    bdraw.ellipse(outer, fill=bg)
    bdraw.ellipse(inner, fill=(0,0,0,0))

    fg_layer = Image.new("RGBA", size, (0,0,0,0))
    fdraw = ImageDraw.Draw(fg_layer)
    start = -90
    end = start + int(360 * max(0.0, min(pct, 1.0)))
    fdraw.pieslice(outer, start=start, end=end, fill=fg)

    # cut inner
    inner_mask = Image.new("L", size, 0)
    idraw = ImageDraw.Draw(inner_mask)
    idraw.ellipse(inner, fill=255)
    fg_layer.paste((0,0,0,0), mask=inner_mask)

    ring = Image.alpha_composite(Image.new("RGBA", size, (0,0,0,0)), bg_layer)
    ring = Image.alpha_composite(ring, fg_layer)

    final = Image.new("RGBA", size, (0,0,0,0))
    final.paste(ring, (0,0), mask=mask)
    return final


# -------------------------
# Comic halftone background helper (subtle)
# -------------------------
def apply_halftone_noise(img, intensity=10):
    # apply subtle dots using ImageOps.posterize + blend for comic-like texture
    try:
        grey = img.convert("L").resize(img.size)
        dots = grey.point(lambda p: 255 if p < 200 else 0)
        dots = dots.filter(ImageFilter.GaussianBlur(2)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255,255,255,0))
        overlay.paste((0,0,0,40), (0,0,img.size[0], img.size[1]))
        return Image.alpha_composite(img, overlay)
    except Exception:
        return img


# -------------------------
# MAIN: comic-cover style profile
# -------------------------
def generate_profile_image(user):
    """
    Expects user dict keys:
      user_id, xp_total, xp_current, xp_to_next_level, level, form
    Optional stats (if available):
      wins, mobs_defeated, rituals
    """
    user_id = user.get("user_id", "unknown")
    level = int(user.get("level", 1))
    xp_current = int(user.get("xp_current", 0))
    xp_next = int(user.get("xp_to_next_level", 200) or 200)
    xp_total = int(user.get("xp_total", 0))
    form = user.get("form", "Tadpole")

    # optional stats (fallback to 0)
    wins = int(user.get("wins", 0))
    mobs_defeated = int(user.get("mobs_defeated", user.get("mobs", 0)))
    rituals = int(user.get("rituals", 0))

    # canvas: social share friendly (1200x675) — good for Twitter / Telegram cards
    width, height = 1200, 675
    canvas = Image.new("RGBA", (width, height), (18, 18, 28, 255))

    # background nebula (if present)
    neb_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(neb_path):
        neb = Image.open(neb_path).convert("RGBA").resize((width, height))
        canvas = Image.alpha_composite(canvas, neb)
    else:
        # fallback gradient
        grad = Image.new("RGBA", (width, height), (32, 12, 45, 255))
        canvas = Image.alpha_composite(canvas, grad)

    # apply subtle comic texture
    canvas = apply_halftone_noise(canvas, intensity=6)

    draw = ImageDraw.Draw(canvas)

    # card frame and comic border
    margin = 36
    inner = (margin, margin, width - margin, height - margin)
    # outer border
    draw.rectangle(inner, outline=(255, 200, 80), width=6)
    # inner white border (comic ink)
    inset = 10
    draw.rectangle((inner[0]+inset, inner[1]+inset, inner[2]-inset, inner[3]-inset), outline=(20,20,20), width=3)

    # Title (comic style)
    title = "MEGAGROK — HERO STATS"
    tbox = (inner[0] + 28, inner[1] + 20)
    outline_text(draw, tbox, title, TITLE_FONT, fill=(255,240,200), outline=(40,10,80), stroke=6)

    # Left panel: stats card (light paper)
    left_w = int(width * 0.48)
    left_x0 = inner[0] + 28
    left_y0 = inner[1] + 120
    left_x1 = left_w
    left_y1 = inner[3] - 40

    panel_rect = (left_x0, left_y0, left_x1, left_y1)
    draw.rounded_rectangle(panel_rect, radius=16, fill=(250, 245, 230, 230), outline=(10,10,10), width=2)

    # Decorative comic halftone box for name plate
    name_plate = (left_x0 + 18, left_y0 + 12, left_x1 - 18, left_y0 + 80)
    draw.rectangle(name_plate, fill=(40, 10, 80), outline=(0,0,0), width=2)
    # Name / handle
    name_text = f"User {user_id}"
    outline_text(draw, (name_plate[0] + 18, name_plate[1] + 8), name_text, SUBTITLE_FONT, fill=(255,255,255), outline=(0,0,0), stroke=5)

    # Stats lines positions
    stat_x = left_x0 + 28
    stat_y = name_plate[3] + 18
    line_h = 44

    # Level big
    outline_text(draw, (stat_x, stat_y), f"LEVEL {level}", BIG_FONT, fill=(30,30,30), outline=(240,200,60), stroke=6)
    stat_y += line_h + 10

    # XP bar + numeric
    xp_pct = 0.0 if xp_next <= 0 else max(0.0, min(xp_current / xp_next, 1.0))
    bar_bbox = (stat_x, stat_y, stat_x + 400, stat_y + 32)
    draw_rounded_bar(canvas, bar_bbox, xp_pct, radius=10, bg_color="#dfe6e9", fill_color="#ffca28", outline_color="#000000")
    # XP text (right aligned)
    xp_text = f"XP: {xp_current}/{xp_next} ({int(xp_pct*100)}%)"
    bbox = draw.textbbox((0,0), xp_text, font=SMALL_FONT)
    text_w = bbox[2] - bbox[0]
    draw.text((bar_bbox[2] - text_w, bar_bbox[1] - 28), xp_text, font=SMALL_FONT, fill=(40,40,40))

    stat_y += 56

    # Lifetime XP
    outline_text(draw, (stat_x, stat_y), f"Lifetime XP: {xp_total}", BODY_FONT, fill=(40,40,40), outline=(240,240,240), stroke=2)
    stat_y += line_h

    # Achievements / stats rows
    outline_text(draw, (stat_x, stat_y), f"Wins: {wins}", BODY_FONT, fill=(20,20,20), outline=(240,240,240), stroke=1)
    outline_text(draw, (stat_x + 200, stat_y), f"Mobs: {mobs_defeated}", BODY_FONT, fill=(20,20,20), outline=(240,240,240), stroke=1)
    outline_text(draw, (stat_x + 380, stat_y), f"Rituals: {rituals}", BODY_FONT, fill=(20,20,20), outline=(240,240,240), stroke=1)

    stat_y += line_h + 10

    # Badges strip (loads assets/badges)
    badges_dir = os.path.join(ASSET_DIR, "badges")
    bx = stat_x
    by = stat_y
    if os.path.isdir(badges_dir):
        for fname in sorted(os.listdir(badges_dir))[:6]:
            fpath = os.path.join(badges_dir, fname)
            try:
                bimg = Image.open(fpath).convert("RGBA").resize((64, 64))
                canvas.paste(bimg, (bx, by), bimg)
                bx += 74
            except Exception:
                continue

    # Right area: big hero Grok
    right_cx = int((left_x1 + inner[2]) / 2) + 60
    right_cy = int((left_y0 + left_y1) / 2) - 20

    sprite = None
    try:
        sprite = load_form_image(form)
    except Exception:
        sprite = None

    if sprite:
        # halo
        halo = sprite.copy().convert("RGBA")
        halo = halo.resize((int(sprite.width * 2.2), int(sprite.height * 2.2)))
        halo = halo.filter(ImageFilter.GaussianBlur(36))
        tint = Image.new("RGBA", halo.size, (255, 140, 40, 90))
        halo = Image.alpha_composite(halo, tint)
        hx = right_cx - halo.width // 2
        hy = right_cy - halo.height // 2
        canvas.paste(halo, (hx, hy), halo)

    # XP ring and sprite sized for cover
    ring = draw_xp_ring(canvas.size, (right_cx, right_cy), radius=190, thickness=20, pct=xp_pct, bg=(30,30,40,180), fg=(255,200,60,230))
    canvas = Image.alpha_composite(canvas, ring)

    if sprite:
        sp = sprite.resize((300, 300)).convert("RGBA")
        sx = right_cx - sp.width // 2
        sy = right_cy - sp.height // 2
        canvas.paste(sp, (sx, sy), sp)
    else:
        # fallback silhouette
        draw.ellipse([right_cx-120, right_cy-120, right_cx+120, right_cy+120], fill=(80,80,80))
        outline_text(draw, (right_cx-20, right_cy-18), "??", BIG_FONT, fill=(255,255,255), outline=(0,0,0), stroke=3)

    # bottom-left: callout / share hint
    callout = "Share your Grok — recruit tamers!"
    cbbox = (inner[0]+28, inner[3]-80, inner[0]+420, inner[3]-36)
    draw.rounded_rectangle(cbbox, radius=8, fill=(250,240,210), outline=(10,10,10))
    outline_text(draw, (cbbox[0]+12, cbbox[1]+8), callout, BODY_FONT, fill=(20,20,20), outline=(255,255,255), stroke=2)

    # bottom-right: optional t.me link (small)
    bot_link = "t.me/YourMegaGrokBot"
    bbox_link = draw.textbbox((0,0), bot_link, font=SMALL_FONT)
    wlink = bbox_link[2] - bbox_link[0]
    draw.text((inner[2]-28-wlink, inner[3]-44), bot_link, font=SMALL_FONT, fill=(230,230,230))

    # Save
    out = f"/tmp/profile_{user_id}.png"
    canvas.convert("RGBA").save(out)
    return out


# -------------------------
# Leaderboard generator (keeps previous style)
# -------------------------
def generate_leaderboard_image():
    rows = get_top_users()
    width = 1000
    height = 200 + len(rows) * 140
    img = Image.new("RGBA", (width, height), (10, 5, 20, 255))

    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        neb = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, neb)

    draw = ImageDraw.Draw(img)

    outline_text(draw, (width//2 - 260, 40), "MEGAGROK HOP-FAME", load_font(48), fill=(255, 230, 120), outline=(80,20,100), stroke=6)

    icon_crown = os.path.join(ASSET_DIR, "icon_crown.png")
    icon_xp = os.path.join(ASSET_DIR, "icon_xp.png")
    icon_comic = os.path.join(ASSET_DIR, "icon_comic.png")

    y = 120
    for i, user in enumerate(rows):
        rank = i + 1
        if rank <= 3:
            glow = Image.new("RGBA", (width, 120), (255,220,50,60))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
            img.paste(glow, (0, y - 20), glow)

        draw.rectangle([(40, y), (width-40, y+100)], fill=(255,255,255,22), outline=(255,255,255,50), width=2)
        outline_text(draw, (70, y+20), f"#{rank}", load_font(36), fill=(255,255,200), outline=(0,0,0), stroke=4)

        if rank == 1 and os.path.exists(icon_crown):
            crown = Image.open(icon_crown).convert("RGBA").resize((64,64))
            img.paste(crown, (150, y), crown)

        sprite = load_form_image(user.get("form", "Tadpole"))
        if sprite:
            sprite = sprite.resize((96,96))
            img.paste(sprite, (230, y + 8), sprite)

        outline_text(draw, (340, y + 12), f"User {user['user_id']}", load_font(28), fill=(255,255,255), outline=(0,0,0), stroke=3)
        xp_text = f"Lvl {user.get('level',1)}   {user.get('xp_total',0)} XP"
        draw.text((680, y + 52), xp_text, font=BODY_FONT, fill=(255,255,255))

        y += 120

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
