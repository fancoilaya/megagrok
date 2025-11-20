import random
import os

COMMON = [
    ("Shadow FUDling", 60, 120),
    ("DoomSlime", 50, 110),
    ("Bearcaller", 40, 100),
    ("Market Goblin", 30, 90),
]

RARE = [
    ("Rug Serpent", 80, 160),
    ("Liquidation Beast", 90, 180),
]

EPIC = [
    ("MegaFUD Titan", 150, 300),
]

LEGENDARY = [
    ("Rugnarok Prime", 300, 600),
]

def choose_enemy():
    pool = random.choices(
        [COMMON, RARE, EPIC, LEGENDARY],
        weights=[70, 20, 9, 1],
        k=1
    )[0]
    return random.choice(pool)

def pick_fight_gif():
    folder = os.path.join("assets", "fight_gifs")
    if not os.path.isdir(folder):
        return None
    gifs = [f for f in os.listdir(folder) if f.lower().endswith(".gif")]
    if not gifs:
        return None
    return os.path.join(folder, random.choice(gifs))
