

# bot/images.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from bot.db import get_top_users

ASSET_DIR = "assets"

# ---------------------------------------------------
# FONT LOADING
# ---------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(os.path.join(ASSET_DIR, "Roboto-Bold.ttf"), size)
    except:
        return ImageFont.load_default()

TITLE_FONT   = load_font(56)
BODY_FONT    = load_font(28)
SMALL_FONT   = load_font(20)
STAT_FONT    = load_font(34)
HERO_FONT    = load_font(40)


# ---------------------------------------------------
# OUTLINE TEXT (stroke-safe)
# ---------------------------------------------------
def outline_text(draw, pos, text, font, fill=(255,255,255), outline=(0,0,0), stroke=4):
    draw.text(
        pos,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=outline
    )


# ---------------------------------------------------
# LOAD GROK SPRITE
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


# ---------------------------------------------------
# HALFTONE COMIC TEXTURE
# ---------------------------------------------------
def apply_halftone(img):
    overlay = Image.new("RGBA", img.size, (255,255,255,0))

    dot = Image.new("RGBA", (8,8), (0,0,0,35))

    for y in range(0, img.size[1], 8):
        for x in range(0, img.size[0], 8):
            if (x//8 + y//8) % 2 == 0:
                overlay.paste(dot, (x, y), dot)

    return Image.alpha_composite(img, overlay)


# ---------------------------------------------------
# MAIN PROFILE TRADING CARD
# ---------------------------------------------------
def generate_profile_image(user):

    # --- Extract user fields ---
    user_id        = user.get("user_id", "unknown")
    form           = user.get("form", "Tadpole")
    level          = int(user.get("level", 1))
    xp_current     = int(user.get("xp_current", 0))
    xp_next        = int(user.get("xp_to_next_level", 200))
    wins           = int(user.get("wins", 0))
    mobs           = int(user.get("mobs_defeated", 0))
    rituals        = int(user.get("rituals", 0))

    # --- Percentage ---
    pct = 0
    if xp_next > 0:
        pct = max(0, min(1, xp_current / xp_next))

    # --- Canvas ---
    width, height = 900, 1280
    canvas = Image.new("RGBA", (width, height), (255, 249, 230, 255))

    # --- Nebula background ---
    neb_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(neb_path):
        neb = Image.open(neb_path).convert("RGBA").resize((width, height))
        # blended matte
        neb = Image.blend(Image.new("RGBA", neb.size, (255,255,240,255)), neb, 0.32)
        canvas = Image.alpha_composite(canvas, neb)

    # --- Comic halftone ---
    canvas = apply_halftone(canvas)

    draw = ImageDraw.Draw(canvas)

    # ---------------------------------------------------
    # COMIC BORDER
    # ---------------------------------------------------
    margin = 26
    outer = (margin, margin, width - margin, height - margin)

    # thick outer black border
    draw.rectangle(outer, outline=(0,0,0), width=10)

    # yellow inset border
    inset = 14
    yellow_rect = (
        outer[0] + inset,
        outer[1] + inset,
        outer[2] - inset,
        outer[3] - inset
    )
    draw.rectangle(yellow_rect, outline=(255,215,80), width=8)

    # white comic inner border
    inner = (
        yellow_rect[0] + 10,
        yellow_rect[1] + 10,
        yellow_rect[2] - 10,
        yellow_rect[3] - 10
    )
    draw.rectangle(inner, outline=(30,30,30), width=4)


    # ---------------------------------------------------
    # TITLE
    # ---------------------------------------------------
    outline_text(
        draw,
        (inner[0] + 30, inner[1] + 20),
        "MEGAGROK: HERO PROFILE",
        TITLE_FONT,
        fill=(250,240,200),
        outline=(40,10,80),
        stroke=6
    )


    # ---------------------------------------------------
    # HERO (centered)
    # ---------------------------------------------------
    sprite = load_form_image(form)
    hero_cx = width // 2
    hero_cy = inner[1] + 380

    # halo
    if sprite:
        halo = sprite.copy().resize((int(sprite.width*2.4), int(sprite.height*2.4)))
        halo = halo.convert("RGBA").filter(ImageFilter.GaussianBlur(42))

        tint = Image.new("RGBA", halo.size, (255,180,60,90))
        halo = Image.alpha_composite(halo, tint)

        hx = hero_cx - halo.width//2
        hy = hero_cy - halo.height//2
        canvas.paste(halo, (hx,hy), halo)

    # main sprite (no XP ring)
    if sprite:
        sp = sprite.resize((420, 420)).convert("RGBA")
        sx = hero_cx - sp.width//2
        sy = hero_cy - sp.height//2
        canvas.paste(sp, (sx, sy), sp)
    else:
        draw.ellipse([hero_cx-200, hero_cy-200, hero_cx+200, hero_cy+200], fill=(70,70,70))


    # ---------------------------------------------------
    # BOTTOM STATS BAR
    # ---------------------------------------------------
    bar_h = 240
    bar_top = inner[3] - bar_h

    bar_rect = (
        inner[0] + 30,
        bar_top,
        inner[2] - 30,
        inner[3] - 30
    )
    draw.rounded_rectangle(bar_rect, radius=20, fill=(255,245,205), outline=(0,0,0), width=5)

    bx = bar_rect[0] + 36
    by = bar_rect[1] + 26

    # Level
    outline_text(draw, (bx, by), f"LEVEL {level}", HERO_FONT,
                 fill=(20,20,20), outline=(255,200,40), stroke=4)

    by += 70

    # XP
    outline_text(draw, (bx, by),
                 f"XP {xp_current}/{xp_next}  ({int(pct*100)}%)",
                 BODY_FONT,
                 fill=(40,40,40), outline=(255,200,40), stroke=2)

    by += 60

    # Win / mobs / rituals row
    outline_text(draw, (bx, by), f"WINS: {wins}", BODY_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (bx+260, by), f"MOBS: {mobs}", BODY_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2)
    outline_text(draw, (bx+500, by), f"RITUALS: {rituals}", BODY_FONT,
                 fill=(20,20,20), outline=(255,255,255), stroke=2)


    # ---------------------------------------------------
    # BADGES ROW
    # ---------------------------------------------------
    badges_dir = os.path.join(ASSET_DIR, "badges")
    if os.path.isdir(badges_dir):
        bx_badge = bar_rect[0] + 36
        by_badge = bar_rect[3] - 100

        for fname in sorted(os.listdir(badges_dir))[:6]:
            path = os.path.join(badges_dir, fname)
            try:
                badge = Image.open(path).convert("RGBA").resize((72,72))
                canvas.paste(badge, (bx_badge, by_badge), badge)
                bx_badge += 86
            except:
                continue


    # ---------------------------------------------------
    # FOOTER LINK
    # ---------------------------------------------------
    footer = "t.me/YourMegaGrokBot"
    draw.text((inner[2]-20 - draw.textbbox((0,0), footer, font=SMALL_FONT)[2],
               inner[3] - 40),
               footer,
               font=SMALL_FONT,
               fill=(50,50,50))


    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------
    out = f"/tmp/profile_{user_id}.png"
    canvas.save(out)
    return out


# ---------------------------------------------------
# LEADERBOARD (unchanged style)
# ---------------------------------------------------
def generate_leaderboard_image():
    rows = get_top_users()

    width = 1000
    height = 200 + len(rows)*140
    img = Image.new("RGBA", (width,height), (22,18,40,255))

    neb_path = os.path.join(ASSET_DIR, "nebula_bg.png")
    if os.path.exists(neb_path):
        neb = Image.open(neb_path).convert("RGBA").resize((width,height))
        img = Image.alpha_composite(img, neb)

    draw = ImageDraw.Draw(img)

    outline_text(draw, (width//2 - 260, 40),
                 "MEGAGROK HOP-FAME",
                 load_font(56),
                 fill=(255,230,140),
                 outline=(40,0,80), stroke=6)

    y = 160

    for i, user in enumerate(rows):
        rank = i+1

        draw.rectangle([(40,y),(width-40,y+110)],
                       outline=(255,255,255,60), width=2)

        outline_text(draw, (60, y+30), f"#{rank}",
                     HERO_FONT, fill=(255,255,180),
                     outline=(0,0,0), stroke=4)

        sprite = load_form_image(user.get("form","Tadpole"))
        if sprite:
            sp = sprite.resize((110,110))
            img.paste(sp,(180,y),sp)

        outline_text(draw, (350,y+20),
                     f"User {user['user_id']}",
                     BODY_FONT, fill=(255,255,255),
                     outline=(0,0,0), stroke=3)

        draw.text((350,y+70),
                  f"Lvl {user.get('level',1)} — {user.get('xp_total',0)} XP",
                  font=SMALL_FONT,
                  fill=(255,255,255))

        y += 140

    out = "/tmp/leaderboard.png"
    img.save(out)
    return out

