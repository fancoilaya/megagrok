import random

# ------------------------------
# Mob Database
# ------------------------------

MOBS = [
    {
        "name": "FUDling",
        "min_xp_win": 50,
        "max_xp_win": 150,
        "min_xp_fail": 10,
        "max_xp_fail": 25,
        "gif": "fudling.gif"
    },
    {
        "name": "Bear Goblin",
        "min_xp_win": 70,
        "max_xp_win": 180,
        "min_xp_fail": 15,
        "max_xp_fail": 35,
        "gif": "bear_goblin.gif"
    },
    {
        "name": "Rug Serpent",
        "min_xp_win": 100,
        "max_xp_win": 220,
        "min_xp_fail": 20,
        "max_xp_fail": 40,
        "gif": "rug_serpent.gif"
    },
    {
        "name": "Liquidity Phantom",
        "min_xp_win": 120,
        "max_xp_win": 260,
        "min_xp_fail": 25,
        "max_xp_fail": 50,
        "gif": "liq_phantom.gif"
    },
    {
        "name": "The Gas Fiend",
        "min_xp_win": 80,
        "max_xp_win": 200,
        "min_xp_fail": 15,
        "max_xp_fail": 30,
        "gif": "gas_fiend.gif"
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

