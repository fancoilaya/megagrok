import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING
# ---------------------------------------------------
def load_font(size):
    """Load font from assets or fallback."""
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

DEFAULT_FONT = load_font(28)


# ---------------------------------------------------
# OUTLINE TEXT
# ---------------------------------------------------
def outline_text(draw, pos, text, font, fill, outline="black", stroke=3, anchor=None):
    draw.text(
        pos,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline,
        anchor=anchor,
    )


# ---------------------------------------------------
# GROK SPRITES
# ---------------------------------------------------
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
# Helper: Rounded Gradient Bar
# -------------------------
def draw_rounded_bar(base_img, bbox, pct, radius=12, bg_color="#2b2b2b", fill_color="#00FF66", outline_color=None):
    """
    Draw a rounded progress bar on base_img.
    bbox = (x0, y0, x1, y1)
    pct between 0..1
    """
    draw = ImageDraw.Draw(base_img)
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    # Background
    draw.rounded_rectangle(bbox, radius=radius, fill=bg_color)
    # Fill width
    fill_w = max(2, int(width * max(0, min(pct, 1))))
    if fill_w > 2:
        fill_bbox = (x0, y0, x0 + fill_w, y1)
        draw.rounded_rectangle(fill_bbox, radius=radius, fill=fill_color)
    # Outline
    if outline_color:
        draw.rounded_rectangle(bbox, radius=radius, outline=outline_color, width=2)


# -------------------------
# Helper: Circular XP Ring
# -------------------------
def draw_xp_ring(size, center, radius, thickness, pct, bg=(40, 40, 50, 200), fg=(0, 230, 140, 230)):
    """
    Returns an RGBA image sized `size` with a circular ring drawn.
    center: (cx, cy)
    radius: outer radius
    thickness: ring thickness in px
    pct: fill fraction 0..1
    """
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    cx, cy = center
    outer = [cx - radius, cy - radius, cx + radius, cy + radius]
    inner = [cx - (radius - thickness), cy - (radius - thickness), cx + (radius - thickness), cy + (radius - thickness)]

    # Create mask for ring shape
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(outer, fill=255)
    md.ellipse(inner, fill=0)

    # Background ring
    bg_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_layer)
    bg_draw.ellipse(outer, fill=bg)
    bg_draw.ellipse(inner, fill=(0, 0, 0, 0))

    # Foreground pieslice for pct
    fg_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg_layer)
    start_angle = -90
    end_angle = start_angle + int(360 * max(0, min(pct, 1.0)))
    fd.pieslice(outer, start=start_angle, end=end_angle, fill=fg)

    # Cut inner circle out of fg_layer to make ring
    inner_mask = Image.new("L", size, 0)
    idraw = ImageDraw.Draw(inner_mask)
    idraw.ellipse(inner, fill=255)
    fg_layer.paste((0, 0, 0, 0), mask=inner_mask)

    # Composite and mask to ring shape
    ring = Image.alpha_composite(Image.new("RGBA", size, (0, 0, 0, 0)), bg_layer)
    ring = Image.alpha_composite(ring, fg_layer)

    final = Image.new("RGBA", size, (0, 0, 0, 0))
    final.paste(ring, (0, 0), mask=mask)
    return final


# ---------------------------------------------------
# PROFILE IMAGE (UPGRADED)
# ---------------------------------------------------
def generate_profile_image(user):
    """
    Upgraded profile image generator.

    Input user dict expected fields:
      user_id, xp_total, xp_current, xp_to_next_level, level, form
    """
    user_id = user.get("user_id", "unknown")
    level = user.get("level", 1)
    xp_current = user.get("xp_current", 0)
    xp_next = user.get("xp_to_next_level", 200)
    xp_total = user.get("xp_total", 0)
    form = user.get("form", "Tadpole")

    # Canvas
    width, height = 900, 520
    canvas = Image.new("RGBA", (width, height), (18, 18, 28, 255))

    # Nebula background if available
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        neb = Image.open(nebula_path).convert("RGBA").resize((width, height))
        canvas = Image.alpha_composite(canvas, neb)

    draw = ImageDraw.Draw(canvas)

    # Outer frame glow
    frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle([(8, 8), (width-9, height-9)], radius=24, outline=(10, 220, 180, 255), width=6)
    frame = frame.filter(ImageFilter.GaussianBlur(8))
    canvas = Image.alpha_composite(canvas, frame)

    # Main card inner panel
    panel_margin = 30
    panel_bbox = (panel_margin, panel_margin, width - panel_margin, height - panel_margin)
    draw.rounded_rectangle(panel_bbox, radius=20, fill=(14, 14, 20, 200))

    # Left region = stats; Right region = sprite
    left_w = int(width * 0.52)
    right_x = left_w + 40

    # Title plate
    title_font = load_font(42)
    title_text = "MEGAGROK PROFILE"
    plate_bbox = (panel_margin + 20, panel_margin + 12, left_w - 10, panel_margin + 72)
    draw.rounded_rectangle(plate_bbox, radius=8, fill=(30, 20, 60, 200))
    draw.text((plate_bbox[0] + 18, plate_bbox[1] + 8), title_text, font=title_font, fill=(255, 240, 220))

    # Left-side basic info
    label_font = load_font(22)
    big_font = load_font(36)
    small_font = load_font(18)

    info_x = panel_margin + 40
    info_y = panel_margin + 110

    draw.text((info_x, info_y), f"User: {user_id}", font=label_font, fill=(220, 220, 230))
    draw.text((info_x, info_y + 40), f"Level: {level}", font=big_font, fill=(255, 255, 255))
    draw.text((info_x, info_y + 90), f"Form: {form}", font=label_font, fill=(200, 200, 220))

    # XP bar area
    xp_pct = 0.0 if xp_next <= 0 else max(0.0, min(xp_current / xp_next, 1.0))
    bar_bbox = (info_x, info_y + 140, info_x + 420, info_y + 190)
    draw_rounded_bar(canvas, bar_bbox, xp_pct, radius=12, bg_color="#222233", fill_color="#00E676", outline_color="#7FFFD4")
    # XP numeric + percent
    pct_text = f"{int(xp_pct * 100)}%"
    draw.text((bar_bbox[0] + 8, bar_bbox[1] - 30), f"XP: {xp_current}/{xp_next}", font=label_font, fill=(200, 200, 220))
    draw.text((bar_bbox[2] - 70, bar_bbox[1] - 30), pct_text, font=label_font, fill=(200, 200, 220))

    # Lifetime XP and small stats
    stats_y = info_y + 220
    draw.text((info_x, stats_y), f"Lifetime XP: {xp_total}", font=small_font, fill=(180, 180, 200))
    draw.text((info_x, stats_y + 28), f"Rituals: —   Fights: —   Wins: —", font=small_font, fill=(160, 160, 180))

    # Badges area (loads images from assets/badges/)
    badge_dir = os.path.join(ASSET_DIR, "badges")
    if os.path.isdir(badge_dir):
        bx = info_x
        by = stats_y + 68
        for fname in sorted(os.listdir(badge_dir))[:5]:
            fpath = os.path.join(badge_dir, fname)
            try:
                bimg = Image.open(fpath).convert("RGBA").resize((56, 56))
                canvas.paste(bimg, (bx, by), bimg)
                bx += 66
            except Exception:
                continue

    # RIGHT side: Grok sprite + XP ring
    sprite = None
    try:
        sprite = load_form_image(form)
    except Exception:
        sprite = None

    # Sprite placement center
    sprite_cx = right_x + (width - right_x) // 2
    sprite_cy = panel_margin + 230

    # Draw halo behind sprite if sprite exists
    if sprite:
        halo = sprite.copy().convert("RGBA")
        halo = halo.resize((int(sprite.width * 2.0), int(sprite.height * 2.0)))
        halo = halo.filter(ImageFilter.GaussianBlur(24))
        tint = Image.new("RGBA", halo.size, (8, 200, 150, 80))
        halo = Image.alpha_composite(halo, tint)
        hx = sprite_cx - halo.width // 2
        hy = sprite_cy - halo.height // 2
        canvas.paste(halo, (hx, hy), halo)

    # Draw XP ring around the sprite
    ring_size = canvas.size
    ring = draw_xp_ring(ring_size, (sprite_cx, sprite_cy), radius=120, thickness=14, pct=xp_pct, bg=(40, 40, 50, 200), fg=(0, 230, 140, 230))
    canvas = Image.alpha_composite(canvas, ring)

    # Draw main sprite
    if sprite:
        s = sprite.resize((200, 200)).convert("RGBA")
        sx = sprite_cx - s.width // 2
        sy = sprite_cy - s.height // 2
        canvas.paste(s, (sx, sy), s)
    else:
        draw.ellipse([sprite_cx - 80, sprite_cy - 80, sprite_cx + 80, sprite_cy + 80], fill=(60, 60, 70))
        draw.text((sprite_cx - 20, sprite_cy - 10), "??", font=big_font, fill=(220, 220, 220))

    # Small level badge centered on the ring
    lvl_badge_radius = 28
    badge_box = [sprite_cx - lvl_badge_radius, sprite_cy + 90, sprite_cx + lvl_badge_radius, sprite_cy + 90 + lvl_badge_radius*2]
    draw.ellipse(badge_box, fill=(20, 150, 110))
    # draw level number centered in the badge
    level_text = str(level)
    w, h = draw.textsize(level_text, font=big_font)
    draw.text((sprite_cx - w//2, sprite_cy + 98), level_text, font=big_font, fill=(255, 255, 255))

    # Save
    out_path = f"/tmp/profile_{user_id}.png"
    canvas.convert("RGBA").save(out_path)
    return out_path


# ---------------------------------------------------
# LEADERBOARD IMAGE (FIXED)
# ---------------------------------------------------
def generate_leaderboard_image():
    rows = get_top_users()  # each user contains xp_total, xp_current, xp_to_next_level, level, form

    width = 1000
    height = 200 + len(rows) * 140
    img = Image.new("RGBA", (width, height), (10, 5, 20, 255))

    # Nebula background
    nebula_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(nebula_path):
        neb = Image.open(nebula_path).convert("RGBA").resize((width, height))
        img = Image.alpha_composite(img, neb)

    draw = ImageDraw.Draw(img)

    # Title
    outline_text(
        draw, (width // 2, 80),
        "MEGAGROK HOP-FAME",
        load_font(70),
        fill=(255, 230, 120),
        outline="purple",
        stroke=6,
        anchor="mm"
    )

    icon_crown = os.path.join(ASSET_DIR, "icon_crown.png")
    icon_xp = os.path.join(ASSET_DIR, "icon_xp.png")
    icon_comic = os.path.join(ASSET_DIR, "icon_comic.png")

    y = 180

    for i, user in enumerate(rows):
        rank = i + 1

        # Glow for top 3
        if rank <= 3:
            glow = Image.new("RGBA", (width, 140), (255, 220, 50, 60))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
            img.paste(glow, (0, y - 20), glow)

        # Row background box
        draw.rectangle(
            [(40, y), (width - 40, y + 120)],
            fill=(255, 255, 255, 22),
            outline=(255, 255, 255, 50),
            width=2
        )

        # Rank text
        outline_text(draw, (70, y + 35), f"#{rank}", load_font(48),
                     fill=(255, 255, 200), outline="black", stroke=4)

        # Crown for first place
        if rank == 1 and os.path.exists(icon_crown):
            crown = Image.open(icon_crown).convert("RGBA").resize((70, 70))
            img.paste(crown, (150, y - 5), crown)

        # Grok sprite
        sprite = load_form_image(user["form"])
        if sprite:
            sprite = sprite.resize((110, 110))
            img.paste(sprite, (240, y + 5), sprite)

        # Username
        outline_text(
            draw,
            (380, y + 15),
            f"User {user['user_id']}",
            load_font(36),
            fill="white",
            outline="black",
            stroke=4
        )

        # XP + Level
        xp_text = f"Lvl {user['level']}    {user.get('xp_total', 0)} XP"

        if os.path.exists(icon_xp):
            xp_ic = Image.open(icon_xp).convert("RGBA").resize((36, 36))
            img.paste(xp_ic, (380, y + 65), xp_ic)

        outline_text(
            draw,
            (430, y + 65),
            xp_text,
            load_font(30),
            fill="white",
            outline="black",
            stroke=3
        )

        # Comic FX for top rankings
        if rank <= 3 and os.path.exists(icon_comic):
            fx = Image.open(icon_comic).convert("RGBA").resize((90, 90))
            img.paste(fx, (width - 160, y + 15), fx)

        y += 140

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out
