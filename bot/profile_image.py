# bot/profile_image.py
# MEGAGROK PROFILE CARD v3 — Comic Trading Card Edition
# Includes:
#  - Dynamic halftone explosion background based on evolution stage
#  - Comic burst rank badge
#  - Comic headline
#  - XP bar
#  - Stats tiles (wins, fights, rituals, power)
#  - Portrait frame

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageFilter

FONT_PATH = "assets/fonts/megagrok.ttf"   # replace with your font file
DEFAULT_FONT = "DejaVuSans-Bold.ttf"

# ---------------------------------------------------------
# SAFE FONT LOADER
# ---------------------------------------------------------
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.truetype(DEFAULT_FONT, size)

# ---------------------------------------------------------
# TEXT SIZE HANDLER
# ---------------------------------------------------------
def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return (bbox[2]-bbox[0], bbox[3]-bbox[1])

# ---------------------------------------------------------
# OUTLINE TEXT
# ---------------------------------------------------------
def draw_outline(draw, xy, text, font, fill, outline=(0,0,0), w=3):
    x,y = xy
    for dx in range(-w, w+1):
        for dy in range(-w, w+1):
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text((x,y), text, font=font, fill=fill)

# ---------------------------------------------------------
# HALFTONE EXPLOSION BG BASED ON STAGE
# ---------------------------------------------------------
def generate_halftone(stage, size=(220,220)):
    w,h = size
    base = Image.new("RGB", size, (40,40,40))
    dr = ImageDraw.Draw(base)

    # Colors per evolution stage
    COLORS = {
        1: ("#33FF55", "#0A5015"),
        2: ("#35D1FF", "#0A3045"),
        3: ("#FF8A00", "#451F00"),
        4: ("#A243FF", "#2A0045"),
        5: ("#FFD93D", "#4D3B00"),
    }

    c1, c2 = COLORS.get(stage, COLORS[1])

    # radial burst lines
    for i in range(24):
        angle = (i / 24) * math.tau
        x = w/2 + math.cos(angle) * w
        y = h/2 + math.sin(angle) * h
        dr.line((w/2, h/2, x, y), fill=c1, width=3)

    # halftone dots
    for y in range(0, h, 12):
        for x in range(0, w, 12):
            if (x+y) % 24 == 0:
                dr.ellipse((x, y, x+6, y+6), fill=c2)

    # soft glow
    return base.filter(ImageFilter.GaussianBlur(2))

# ---------------------------------------------------------
# COMIC RANK BADGE
# ---------------------------------------------------------
def draw_rank_badge(draw, rank, x, y):
    if not rank:
        return
    # rank colors
    colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
    col = colors[rank-1] if rank <= 3 else "#3A3A3A"

    burst_r = 32
    cx,cy = x+burst_r, y+burst_r

    # explosion points
    pts=[]
    for i in range(16):
        ang = i * math.pi*2/16
        r = burst_r if i%2==0 else burst_r*0.6
        pts.append((cx+math.cos(ang)*r, cy+math.sin(ang)*r))

    draw.polygon(pts, fill=col, outline="black")

    # center circle
    draw.ellipse((cx-18,cy-18,cx+18,cy+18), fill="white", outline="black")

    # rank number
    font = load_font(28)
    tw,th = text_size(draw, str(rank), font)
    draw.text((cx-tw/2, cy-th/2), str(rank), font=font, fill="black")

# ---------------------------------------------------------
# MAIN PROFILE IMAGE GENERATOR
# ---------------------------------------------------------
def generate_profile_image(payload):
    user_id = payload["user_id"]
    username = payload.get("username","User")
    level = payload.get("level",1)
    xp = payload.get("xp_total",0)
    wins = payload.get("wins",0)
    fights = payload.get("fights",0)
    rituals = payload.get("rituals",0)
    stage = payload.get("form",1)
    rank = payload.get("rank", None)

    # ------------------ CANVAS ------------------
    W,H=1080,1920
    img = Image.new("RGB",(W,H),(20,20,20))
    dr = ImageDraw.Draw(img)

    # ------------------ TITLE ------------------
    title_font = load_font(120)
    title = "MEGAGROK PROFILE"
    tw,th = text_size(dr,title,title_font)
    draw_outline(dr, ((W-tw)//2, 80), title, title_font, fill="#FFB545")

    # ------------------ RANK BADGE ------------------
    draw_rank_badge(dr, rank, 860, 80)

    # ------------------ PORTRAIT FRAME ------------------
    px,py = 120, 280
    pw,ph = 220,220
    frame = Image.new("RGB",(pw+20,ph+20),(255,255,255))
    img.paste(frame,(px-10,py-10))

    # halftone explosion bg
    halo = generate_halftone(stage, size=(pw,ph))
    img.paste(halo,(px,py))

    # ------------------ USERNAME + LV ------------------
    name_font = load_font(72)
    lv_font = load_font(48)

    nx = px + pw + 80
    ny = py + 10

    draw_outline(dr, (nx,ny), username, name_font, fill="#7EF2FF")

    lv_text = f"LV {level} • {xp} XP"
    draw_outline(dr, (nx, ny+90), lv_text, lv_font, fill="#FFB545")

    # ------------------ XP BAR ------------------
    bar_x = nx
    bar_y = ny+160
    bar_w = 500
    bar_h = 32

    dr.rounded_rectangle((bar_x,bar_y,bar_x+bar_w,bar_y+bar_h),
                         fill="#333333", radius=12)

    pct = min(1.0, xp/ max(1,payload.get("xp_to_next",100)))
    fill_w = int(bar_w * pct)

    dr.rounded_rectangle((bar_x,bar_y,bar_x+fill_w,bar_y+bar_h),
                         fill="#7EF2FF", radius=12)

    # ------------------ STATS TILES ------------------
    tile_y = py + ph + 180
    tile_w = 240
    tile_h = 140
    gap = 32

    stats = [
        ("WINS", wins),
        ("FIGHTS", fights),
        ("RITUALS", rituals),
        ("POWER", level*5 + wins*2),
    ]

    tile_font_label = load_font(42)
    tile_font_num = load_font(60)

    x0 = (W - (tile_w*4 + gap*3))//2

    for i,(label,val) in enumerate(stats):
        tx = x0 + i*(tile_w+gap)
        dr.rounded_rectangle((tx,tile_y,tx+tile_w,tile_y+tile_h),
                             fill="#1E1E1E", radius=20, outline="#FFB545", width=3)

        lw,lh = text_size(dr,label,tile_font_label)
        draw_outline(dr, (tx+(tile_w-lw)//2, tile_y+10),
                     label, tile_font_label, fill="white")

        val = str(val)
        vw,vh = text_size(dr,val,tile_font_num)
        draw_outline(dr, (tx+(tile_w-vw)//2, tile_y+60),
                     val, tile_font_num, fill="#FFB545")

    # ------------------ FOOTER ------------------
    foot_font = load_font(48)
    footer = "MegaGrok Metaverse"
    fw,fh = text_size(dr, footer, foot_font)
    draw_outline(dr, ((W-fw)//2, H-160), footer, foot_font, fill="#777777")

    # ------------------ SAVE FILE ------------------
    out = f"/tmp/profile_{user_id}.jpg"
    img.save(out, quality=95)
    return out
