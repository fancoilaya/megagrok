import random

# ------------------------------
# Mob Database
# ------------------------------

MOBS = [
    {
        "name": "FUDling",
        "intro": "A sneaky FUDling appears spreading doubt!",
        "win_text": "You blasted the FUDling into oblivion! 💥",
        "lose_text": "The FUDling confused you, but you still learned something.",
        "min_xp": 50,
        "max_xp": 150,
        "portrait": "assets/mobs/fudling.png",
        "gif": "assets/gifs/fight1.gif"
    },
    {
        "name": "Doom Hopper",
        "intro": "A Doom Hopper drops from the sky, croaking menacingly!",
        "win_text": "You out-hopped the Doom Hopper! ⚡",
        "lose_text": "The Doom Hopper overwhelmed you with chaos hops!",
        "min_xp": 40,
        "max_xp": 120,
        "portrait": "assets/mobs/doomhopper.png",
        "gif": "assets/gifs/fight2.gif"
    },
    {
        "name": "FOMO Beast",
        "intro": "The FOMO Beast charges at you at lightspeed!",
        "win_text": "You tamed the FOMO Beast! 🐸🔥",
        "lose_text": "FOMO clouded your mind… but you gained resilience.",
        "min_xp": 60,
        "max_xp": 160,
        "portrait": "assets/mobs/fomobeast.png",
        "gif": "assets/gifs/fight3.gif"
    },
    {
        "name": "Bear Ogre",
        "intro": "A Bear Ogre emerges from the shadows!",
        "win_text": "You slayed the Bear Ogre’s negativity! 🪓",
        "lose_text": "The Bear Ogre smacked you, but wisdom grows!",
        "min_xp": 70,
        "max_xp": 180,
        "portrait": "assets/mobs/bearogre.png",
        "gif": "assets/gifs/fight4.gif"
    },
    {
        "name": "Hop Goblin",
        "intro": "A Hop Goblin cackles and blocks your path!",
        "win_text": "You defeated the Hop Goblin with supreme hop-power!",
        "lose_text": "The Hop Goblin tricked you, but you’ll return stronger.",
        "min_xp": 30,
        "max_xp": 100,
        "portrait": "assets/mobs/hopgoblin.png",
        "gif": "assets/gifs/fight5.gif"
    }
]



# ------------------------------
# Random Mob Generator
# ------------------------------

def get_random_mob():
    return random.choice(MOBS)


# ------------------------------
# Fight Simulation
# ------------------------------

def simulate_fight(mob):
    """
    Returns (won: bool, xp_reward: int)
    """
    win = random.choice([True, False])

    if win:
        xp = random.randint(mob["min_xp_win"], mob["max_xp_win"])
    else:
        xp = random.randint(mob["min_xp_fail"], mob["max_xp_fail"])

    return win, xp

