# bot/mobs.py
# Master Mob Database — MegaGrok Universe v1.0
# Unified 25-mob list with tier mapping and auto-calculated combat stats.
# Replace/extend assets paths as you render portraits & gifs.

import random
from typing import Dict, Any, List

# -------------------------
# Auto stat generator
# -------------------------
def auto_stats(power: int) -> Dict[str, Any]:
    """
    Generate combat stats from combat_power.
    Tweak the formulas here if you want different scaling.
    """
    return {
        "hp": int(80 + (power * 20)),
        "attack": int(6 + (power * 2)),
        "defense": int(3 + (power * 1)),
        "crit_chance": round(0.02 + (power * 0.01), 3),
        "dodge_chance": round(0.01 + (power * 0.005), 3),
    }

# -------------------------
# TIERS mapping
# -------------------------
TIERS = {
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary"
}

# -------------------------
# Master MOBS dict (canonical)
# -------------------------
MOBS: Dict[str, Dict[str, Any]] = {

    # ------------- TIER 1 (Common) -------------
    "FUDling": {
        "name": "FUDling",
        "tier": 1,
        "rarity": "Common",
        "type": "Shadow-Amphibian",
        "description": "A small creature born from fear, uncertainty, and doubt. It feeds on weak charts and shaky hands.",
        "strength": "Spreading panic",
        "weakness": "Confidence",
        "portrait": "assets/mobs/fudling.png",
        "gif": "assets/gifs/fudling.gif",
        "combat_power": 1,
        "drops": ["+XP", "Wisdom Fragment"],
        "intro": "A sneaky FUDling appears spreading doubt!",
        "win_text": "You blasted the FUDling into oblivion! 💥",
        "lose_text": "The FUDling confused you, but you still learned something.",
        "min_xp": 30,
        "max_xp": 80,
    },

    "HopGoblin": {
        "name": "HopGoblin",
        "tier": 1,
        "rarity": "Common",
        "type": "Chaotic Hopper",
        "description": "A mischievous creature that channels raw hop-energy. Often found causing trouble in liquidity pools.",
        "strength": "Fast attacks",
        "weakness": "Calmness",
        "portrait": "assets/mobs/hopgoblin.png",
        "gif": "assets/gifs/hopgoblin.gif",
        "combat_power": 1,
        "drops": ["+XP", "Goblin Tongue"],
        "intro": "A HopGoblin cackles and blocks your path!",
        "win_text": "You defeated the HopGoblin with supreme hop-power!",
        "lose_text": "The HopGoblin tricked you, but you’ll return stronger.",
        "min_xp": 25,
        "max_xp": 70,
    },

    "Croakling": {
        "name": "Croakling",
        "tier": 1,
        "rarity": "Common",
        "type": "Pond Spawn",
        "description": "A tiny frog-gremlin with huge eyes. Playful, but found in packs.",
        "strength": "Swarm tactics",
        "weakness": "Area attacks",
        "portrait": "assets/mobs/croakling.png",
        "gif": "assets/gifs/croakling.gif",
        "combat_power": 1,
        "drops": ["+XP", "Croaklet Scale"],
        "intro": "A group of Croaklings emerge, chirping in unison!",
        "win_text": "You scared them back into the reeds!",
        "lose_text": "They hopped away with a lesson taught.",
        "min_xp": 20,
        "max_xp": 60,
    },

    "RugRat": {
        "name": "RugRat",
        "tier": 1,
        "rarity": "Common",
        "type": "Trickster",
        "description": "A tiny trickster that loves to tangle rugs and wallets alike.",
        "strength": "Stealth",
        "weakness": "Direct combat",
        "portrait": "assets/mobs/rugrat.png",
        "gif": "assets/gifs/rugrat.gif",
        "combat_power": 1,
        "drops": ["+XP", "Rug Thread"],
        "intro": "A RugRat darts out, pulling at your boots!",
        "win_text": "You chased the RugRat away!",
        "lose_text": "The RugRat got away nibbling on your courage.",
        "min_xp": 18,
        "max_xp": 55,
    },

    "HopSlime": {
        "name": "HopSlime",
        "tier": 1,
        "rarity": "Common",
        "type": "Goo",
        "description": "A sticky slime that hums with residual hop-energy.",
        "strength": "Sticky slowdowns",
        "weakness": "Fire/heat",
        "portrait": "assets/mobs/hopslime.png",
        "gif": "assets/gifs/hopslime.gif",
        "combat_power": 2,
        "drops": ["+XP", "Gel Sample"],
        "intro": "A wobbling HopSlime drifts into your path!",
        "win_text": "You dissolved the HopSlime with finesse!",
        "lose_text": "It clung to you, but you learned resilience.",
        "min_xp": 22,
        "max_xp": 65,
    },

    # ------------- TIER 2 (Uncommon) -------------
    "DoomHopper": {
        "name": "DoomHopper",
        "tier": 2,
        "rarity": "Uncommon",
        "type": "Abyssal Hopper",
        "description": "Forged in the Rugnarok depths, DoomHopper leaps through shadows with destructive hop-energy.",
        "strength": "Burst damage",
        "weakness": "Light",
        "portrait": "assets/mobs/doomhopper.png",
        "gif": "assets/gifs/doomhopper.gif",
        "combat_power": 3,
        "drops": ["+XP", "Hopium Core"],
        "intro": "A DoomHopper drops from the sky, croaking menacingly!",
        "win_text": "You out-hopped the DoomHopper! ⚡",
        "lose_text": "The DoomHopper overwhelmed you with chaos hops!",
        "min_xp": 40,
        "max_xp": 120,
    },

    "LiquiDrip": {
        "name": "LiquiDrip",
        "tier": 2,
        "rarity": "Uncommon",
        "type": "Slime",
        "description": "An ooze that leaches liquidity and leaves markets drier.",
        "strength": "Drain over time",
        "weakness": "Burst damage",
        "portrait": "assets/mobs/liquidrip.png",
        "gif": "assets/gifs/liquidrip.gif",
        "combat_power": 2,
        "drops": ["+XP", "Liquidity Residue"],
        "intro": "A slick LiquiDrip slides into position!",
        "win_text": "You scraped the LiquiDrip off your boots!",
        "lose_text": "It drained your momentum—lesson learned.",
        "min_xp": 35,
        "max_xp": 95,
    },

    "PanicPuff": {
        "name": "PanicPuff",
        "tier": 2,
        "rarity": "Uncommon",
        "type": "Gas",
        "description": "A jittery gas cloud that spreads panic to nearby traders.",
        "strength": "Confusion chance",
        "weakness": "Dispersal",
        "portrait": "assets/mobs/panicpuff.png",
        "gif": "assets/gifs/panicpuff.gif",
        "combat_power": 2,
        "drops": ["+XP", "Anxiety Wisps"],
        "intro": "A PanicPuff drifts in, making the air tingle!",
        "win_text": "You dispelled the PanicPuff!",
        "lose_text": "You staggered, but learned to steady your heartbeat.",
        "min_xp": 30,
        "max_xp": 90,
    },

    "GreedImp": {
        "name": "GreedImp",
        "tier": 2,
        "rarity": "Uncommon",
        "type": "Imp",
        "description": "A coin-hoarding imp that chases every spike.",
        "strength": "Loot steals",
        "weakness": "Patience",
        "portrait": "assets/mobs/greedimp.png",
        "gif": "assets/gifs/greedimp.gif",
        "combat_power": 2,
        "drops": ["+XP", "Imp Coin"],
        "intro": "A GreedImp tosses a shiny coin at you!",
        "win_text": "You outwitted the GreedImp and kept the coin!",
        "lose_text": "It pocketed a bit of your resolve.",
        "min_xp": 32,
        "max_xp": 100,
    },

    "FUDSprite": {
        "name": "FUDSprite",
        "tier": 2,
        "rarity": "Uncommon",
        "type": "Elemental",
        "description": "A fickle airborne spirit that whispers doubt into ears.",
        "strength": "Rapid small hits",
        "weakness": "Direct focus",
        "portrait": "assets/mobs/fudsprite.png",
        "gif": "assets/gifs/fudsprite.gif",
        "combat_power": 2,
        "drops": ["+XP", "Sprite Feather"],
        "intro": "A FUDSprite darts around, murmuring unease.",
        "win_text": "You silenced the sprite's whispers!",
        "lose_text": "It slipped away leaving a lesson behind.",
        "min_xp": 28,
        "max_xp": 85,
    },

    # ------------- TIER 3 (Rare) -------------
    "BearOgre": {
        "name": "BearOgre",
        "tier": 3,
        "rarity": "Rare",
        "type": "Market Titan",
        "description": "A colossal brute that awakens whenever markets turn red.",
        "strength": "Tanky HP",
        "weakness": "Bullish Sentiment",
        "portrait": "assets/mobs/bearogre.png",
        "gif": "assets/gifs/bearogre.gif",
        "combat_power": 4,
        "drops": ["+XP", "Bull Talisman"],
        "intro": "A Bear Ogre emerges from the shadows!",
        "win_text": "You slayed the Bear Ogre’s negativity! 🪓",
        "lose_text": "The Bear Ogre smacked you, but wisdom grows!",
        "min_xp": 60,
        "max_xp": 150,
    },

    "BullSerpent": {
        "name": "BullSerpent",
        "tier": 3,
        "rarity": "Rare",
        "type": "Serpent",
        "description": "A serpentine spirit born of bullish momentum with piercing strikes.",
        "strength": "High crit chance",
        "weakness": "Crowd control",
        "portrait": "assets/mobs/bullserpent.png",
        "gif": "assets/gifs/bullserpent.gif",
        "combat_power": 3,
        "drops": ["+XP", "Serpent Scale"],
        "intro": "A BullSerpent coils into view, scales gleaming!",
        "win_text": "You dodged its coils and triumphed!",
        "lose_text": "Its strike left you stunned—but not broken.",
        "min_xp": 55,
        "max_xp": 140,
    },

    "CandleWraith": {
        "name": "CandleWraith",
        "tier": 3,
        "rarity": "Rare",
        "type": "Volatility",
        "description": "A ghost formed from candle chart volatility; its flames shift unpredictably.",
        "strength": "Volatile attacks",
        "weakness": "Stability",
        "portrait": "assets/mobs/candlewraith.png",
        "gif": "assets/gifs/candlewraith.gif",
        "combat_power": 3,
        "drops": ["+XP", "Wraith Ember"],
        "intro": "A CandleWraith flickers into existence!",
        "win_text": "You soothed the Wraith's flames!",
        "lose_text": "Its volatility taught you caution.",
        "min_xp": 58,
        "max_xp": 145,
    },

    "FearHound": {
        "name": "FearHound",
        "tier": 3,
        "rarity": "Rare",
        "type": "Hunter",
        "description": "A spectral canine that hunts those with wavering resolve.",
        "strength": "Tracks weak players",
        "weakness": "Steadiness",
        "portrait": "assets/mobs/fearhound.png",
        "gif": "assets/gifs/fearhound.gif",
        "combat_power": 3,
        "drops": ["+XP", "Hound Fang"],
        "intro": "A FearHound sniffs the air, searching for faint hearts.",
        "win_text": "You tamed the FearHound's chase!",
        "lose_text": "It ran you ragged—but you learned to steady.",
        "min_xp": 52,
        "max_xp": 130,
    },

    "RugFiend": {
        "name": "RugFiend",
        "tier": 3,
        "rarity": "Rare",
        "type": "Demon",
        "description": "A malicious demon that revels in rug-pulls and chaos.",
        "strength": "High burst damage",
        "weakness": "Sustained defense",
        "portrait": "assets/mobs/rugfiend.png",
        "gif": "assets/gifs/rugfiend.gif",
        "combat_power": 4,
        "drops": ["+XP", "Fiend Thread"],
        "intro": "A RugFiend tears at reality with ragged wings!",
        "win_text": "You stitched reality back together!",
        "lose_text": "It shredded your plans—return stronger.",
        "min_xp": 65,
        "max_xp": 160,
    },

    # ------------- TIER 4 (Epic) -------------
    "FomoBeast": {
        "name": "FomoBeast",
        "tier": 4,
        "rarity": "Epic",
        "type": "Parabolic Entity",
        "description": "Born from sudden hype spikes. It grows stronger with every green candle.",
        "strength": "Explosive growth",
        "weakness": "Patience",
        "portrait": "assets/mobs/fomobeast.png",
        "gif": "assets/gifs/fomobeast.gif",
        "combat_power": 5,
        "drops": ["+XP", "FOMO Heart"],
        "intro": "The FomoBeast charges at you at lightspeed!",
        "win_text": "You tamed the FomoBeast! 🐸🔥",
        "lose_text": "FOMO clouded your mind… but you gained resilience.",
        "min_xp": 90,
        "max_xp": 220,
    },

    "LiquidatorAlpha": {
        "name": "LiquidatorAlpha",
        "tier": 4,
        "rarity": "Epic",
        "type": "Executioner",
        "description": "The embodiment of forced liquidation, hunting weak positions mercilessly.",
        "strength": "Aggressive finishing moves",
        "weakness": "Counterplay windows",
        "portrait": "assets/mobs/liquidatoralpha.png",
        "gif": "assets/gifs/liquidatoralpha.gif",
        "combat_power": 5,
        "drops": ["+XP", "Alpha Circuit"],
        "intro": "Liquidator Alpha descends in a rain of red alerts!",
        "win_text": "You outlasted the Liquidator!",
        "lose_text": "Its purge stung, but you survived the lesson.",
        "min_xp": 100,
        "max_xp": 250,
    },

    "RektTitan": {
        "name": "RektTitan",
        "tier": 4,
        "rarity": "Epic",
        "type": "Titan",
        "description": "A massive failed-hope titan birthed from catastrophic losses.",
        "strength": "Devastating single hits",
        "weakness": "Mobility",
        "portrait": "assets/mobs/rekttitan.png",
        "gif": "assets/gifs/rekttitan.gif",
        "combat_power": 5,
        "drops": ["+XP", "Titan Core"],
        "intro": "The Rekt Titan stomps into the arena!",
        "win_text": "You weathered the Titan's blows and prevailed!",
        "lose_text": "It crushed your defenses—rise again stronger.",
        "min_xp": 110,
        "max_xp": 260,
    },

    "HopReaver": {
        "name": "HopReaver",
        "tier": 4,
        "rarity": "Epic",
        "type": "Reaver",
        "description": "A scythe-wielding hop assassin that cuts through momentum.",
        "strength": "High crit and bleed",
        "weakness": "Predictable patterns",
        "portrait": "assets/mobs/hopreaver.png",
        "gif": "assets/gifs/hopreaver.gif",
        "combat_power": 5,
        "drops": ["+XP", "Reaver Shard"],
        "intro": "HopReaver swings a gleaming scythe toward you!",
        "win_text": "You dodged the scythe and sealed the deal!",
        "lose_text": "Its blade found a mark—train harder.",
        "min_xp": 95,
        "max_xp": 230,
    },

    "OraclePhantom": {
        "name": "OraclePhantom",
        "tier": 4,
        "rarity": "Epic",
        "type": "Seer",
        "description": "A phantom that manipulates chart-lines and foretells volatility.",
        "strength": "Dodges & foresight",
        "weakness": "Direct pressure",
        "portrait": "assets/mobs/oraclephantom.png",
        "gif": "assets/gifs/oraclephantom.gif",
        "combat_power": 4,
        "drops": ["+XP", "Oracle Thread"],
        "intro": "Oracle Phantom drifts, chart-ribbons swirling!",
        "win_text": "You unraveled its predictions and won!",
        "lose_text": "Its foresight evaded your attack—try again.",
        "min_xp": 88,
        "max_xp": 210,
    },

    # ------------- TIER 5 (Legendary Bosses) -------------
    "Hopocalypse": {
        "name": "Hopocalypse",
        "tier": 5,
        "rarity": "Legendary",
        "type": "Titanic Entity",
        "description": "A world-ending hop titan whose presence warps markets and reality.",
        "strength": "Cosmic-scale attacks",
        "weakness": "Coordinated strategy",
        "portrait": "assets/mobs/hopocalypse.png",
        "gif": "assets/gifs/hopocalypse.gif",
        "combat_power": 8,
        "drops": ["+XP", "Apocalypse Shard"],
        "intro": "An earth-shattering roar heralds Hopocalypse's arrival!",
        "win_text": "Against all odds, you halted the Hopocalypse!",
        "lose_text": "The world shook — you lived to fight another day.",
        "min_xp": 250,
        "max_xp": 600,
    },

    "RugnarokPrime": {
        "name": "RugnarokPrime",
        "tier": 5,
        "rarity": "Legendary",
        "type": "Rug Demon",
        "description": "The ultimate rug demon whose torn fabric reshapes realities.",
        "strength": "Reality-warping abilities",
        "weakness": "Anchored defenses",
        "portrait": "assets/mobs/rugnarokprime.png",
        "gif": "assets/gifs/rugnarokprime.gif",
        "combat_power": 9,
        "drops": ["+XP", "Rug Prime Shard"],
        "intro": "Torn fabric wings unfold—the Rugnarok Prime descends!",
        "win_text": "You mended the tear and prevailed!",
        "lose_text": "It unraveled your plans; come back stronger.",
        "min_xp": 300,
        "max_xp": 700,
    },

    "ChartShatterDragon": {
        "name": "ChartShatterDragon",
        "tier": 5,
        "rarity": "Legendary",
        "type": "Dragon",
        "description": "A dragon formed from shattered candlestick charts, it breathes volatility.",
        "strength": "Area damage and pressure",
        "weakness": "Sustained defense",
        "portrait": "assets/mobs/chartshatterdragon.png",
        "gif": "assets/gifs/chartshatterdragon.gif",
        "combat_power": 9,
        "drops": ["+XP", "Dragon Shard"],
        "intro": "A draconic silhouette cracks the sky—ChartShatter Dragon arrives!",
        "win_text": "You broke its patterns and won!",
        "lose_text": "Its scales burned your strategy—return wiser.",
        "min_xp": 320,
        "max_xp": 800,
    },

    "MegaFOMOTitan": {
        "name": "MegaFOMOTitan",
        "tier": 5,
        "rarity": "Legendary",
        "type": "Titan",
        "description": "A titan fueled by the frenzy of markets; grows stronger with fear.",
        "strength": "Scaling power",
        "weakness": "Calm coordination",
        "portrait": "assets/mobs/megafomotitan.png",
        "gif": "assets/gifs/megafomotitan.gif",
        "combat_power": 8,
        "drops": ["+XP", "Titan Heart"],
        "intro": "A pulse of FOMO surges as the MegaFOMO Titan stomps in!",
        "win_text": "You overcame the frenzy!",
        "lose_text": "It consumed your haste—learn to wait.",
        "min_xp": 280,
        "max_xp": 720,
    },

    "LiquidityLeviathan": {
        "name": "LiquidityLeviathan",
        "tier": 5,
        "rarity": "Legendary",
        "type": "Leviathan",
        "description": "A deep-sea cosmic monster that controls the tides of liquidity.",
        "strength": "Control over battlefield flow",
        "weakness": "Surface pressure",
        "portrait": "assets/mobs/liquidityleviathan.png",
        "gif": "assets/gifs/liquidityleviathan.gif",
        "combat_power": 10,
        "drops": ["+XP", "Leviathan Core"],
        "intro": "A massive shadow beneath the waves rises—the Liquidity Leviathan!",
        "win_text": "You surfaced victorious against the Leviathan!",
        "lose_text": "Its depths swallowed your strength—return prepared.",
        "min_xp": 350,
        "max_xp": 900,
    },
}

# -------------------------
# Inject auto stats into each mob
# -------------------------
for key, mob in MOBS.items():
    if "combat_power" in mob:
        mob.update(auto_stats(int(mob["combat_power"])))

# -------------------------
# Helper functions
# -------------------------
def get_mob(name: str) -> Dict[str, Any]:
    """Case-insensitive lookup by canonical name or simple name."""
    if not name:
        return None
    name_norm = name.strip()
    # exact key
    if name_norm in MOBS:
        return MOBS[name_norm]
    # try case-insensitive search
    for k, v in MOBS.items():
        if k.lower() == name_norm.lower() or v.get("name", "").lower() == name_norm.lower():
            return v
    return None

def get_random_mob(tier: int = None) -> Dict[str, Any]:
    """Return a random mob. If tier is specified, pick from that tier."""
    choices = []
    for k, m in MOBS.items():
        if tier is None or m.get("tier") == tier:
            choices.append(m)
    if not choices:
        return None
    return random.choice(choices)

def list_mobs_by_tier(tier: int) -> List[Dict[str, Any]]:
    """List mob dicts for a given tier number."""
    return [m for m in MOBS.values() if m.get("tier") == tier]

def list_all_mobs() -> List[Dict[str, Any]]:
    return list(MOBS.values())
