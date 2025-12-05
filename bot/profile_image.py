# bot/profile_image.py
# ------------------------------------------------------------
# MegaGrok Comic-Style Profile Card Generator (1080×1920)
# ------------------------------------------------------------

from PIL import Image, ImageDraw, ImageFont
import os
import time

CANVAS_W = 1080
CANVAS_H = 1920

FONT_PATHS = [
    "assets/fonts/megagrok_bold.ttf",
    "/var/data/megagrok_bold.ttf",
]

def _load_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()

def _draw_text(draw, x, y, text, font, fill, outline=(20,10,40)):
    for dx in (-3,-2,-1,0,1,2,3):
        for dy in (-3,-2,-1,0,1,2,3):
            draw.text((x+dx,y+dy), text, font=font, fill=outline)
    draw.text((x,y), text, font=font, fill=fill)

def _gradient():
    img = Image.new("RGB",(CANVAS_W,CANVAS_H),(8,5,18))
    px = img.load()
    for y in range(CANVAS_H):
        f = y/CANVAS_H
        r = int(8*(1-f) + 28*f)
        g = int(5*(1-f) + 9*f)
        b = int(18*(1-f) + 36*f)
        for x in range(CANVAS_W):
            px[x,y] = (r,g,b)
    return img

def generate_profile_image(user):
    """
    user = {
        "username": str,
        "level": int,
        "xp_total": int,
        "wins": int,
        "kills": int,
        "rituals": int,
        "form": str (optional evolution)
    }
    """
    bg = _gradient()
    draw = ImageDraw.Draw(bg)

    title_font = _load_font(120)
    name_font = _load_font(80)
    stat_font = _load_font(55)
    small_font = _load_font(40)

    # Title
    _draw_text(draw, 100, 80, "MEGAGROK PROFILE", title_font, (255,159,28))

    # Username
    username = user.get("username","Unknown")
    _draw_text(draw, 100, 250, f"@{username}", name_font, (110,231,249))

    # Level
    _draw_text(draw, 100, 400, f"Level: {user.get('level',1)}", stat_font, (255,244,230))

    # XP
    _draw_text(draw, 100, 500, f"Total XP: {user.get('xp_total',0)}", stat_font, (255,244,230))

    # Wins / Kills / Rituals
    _draw_text(draw, 100, 650,  f"Wins: {user.get('wins',0)}", stat_font, (255,220,180))
    _draw_text(draw, 100, 730,  f"Mob Kills: {user.get('kills',0)}", stat_font, (255,220,180))
    _draw_text(draw, 100, 810,  f"Rituals: {user.get('rituals',0)}", stat_font, (255,220,180))

    # Evolution (if any)
    evo = user.get("form")
    if evo:
        _draw_text(draw, 100, 950, f"Evolution: {evo}", stat_font, (255,180,250))

    # Footer
    draw.text((100, CANVAS_H-120), "t.me/megagrok", font=small_font, fill=(200,180,140))

    # save
    out = f"/var/data/profile_{int(time.time())}.png"
    try:
        bg.save(out,"PNG")
        return out
    except:
        fallback=f"/tmp/profile_{int(time.time())}.png"
        bg.save(fallback,"PNG")
        return fallback
