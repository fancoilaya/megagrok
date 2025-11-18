
import os
import random
import datetime
from telegram.ext import Updater, CommandHandler
from telegram.constants import ParseMode

TOKEN = os.getenv("TELEGRAM_TOKEN")

users = {}

EVOLUTIONS = [
    (1, "Tadpole"),
    (5, "Hopling"),
    (10, "Meme Adept"),
    (20, "Quantum Frog"),
    (35, "Multiverse Hopper"),
    (50, "ULTRAHOP EMERGENCE")
]

TIERS = [
    (1, "Meme Apprentice"),
    (10, "Meme Adept"),
    (20, "Reality Hopper"),
    (35, "Chrono Frog"),
    (50, "ULTRAHOP ASCENDANT")
]

def get_stage(level, table):
    stage = table[0][1]
    for lvl, name in table:
        if level >= lvl:
            stage = name
    return stage

def grow(update, context):
    user_id = update.effective_user.id
    now = datetime.datetime.utcnow()

    if user_id not in users:
        users[user_id] = {"level": 1, "xp": 0, "last_grow": None}

    user = users[user_id]

    if user["last_grow"] and (now - user["last_grow"]).days < 1:
        update.message.reply_text("⏳ You can only grow once every 24 hours!")
        return

    xp_gain = random.randint(5, 20)
    old_level = user["level"]
    old_tier = get_stage(old_level, TIERS)

    user["xp"] += xp_gain
    user["last_grow"] = now
    user["level"] = user["xp"] // 10 + 1
    new_level = user["level"]
    new_tier = get_stage(new_level, TIERS)

    evolution = get_stage(new_level, EVOLUTIONS)

    msg = (
        f"🎉 Your MegaGrok absorbed cosmic hop-energy!"
        f"You gained *{xp_gain} XP* today."
        f"Current Level: {old_level} → {new_level}"
        f"HopForce Tier: {old_tier} → {new_tier}"
        f"Evolution: {evolution}"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

def mygrok(update, context):
    user_id = update.effective_user.id
    if user_id not in users:
        update.message.reply_text("You haven't started yet! Use /growmygrok.")
        return

    user = users[user_id]
    evolution = get_stage(user["level"], EVOLUTIONS)
    tier = get_stage(user["level"], TIERS)

    msg = (
        f"🐸 *MegaGrok Profile*"
        f"Level: {user['level']}"
        f"XP: {user['xp']}"
        f"Evolution: {evolution}"
        f"HopForce Tier: {tier}"
        f"[ASCII Art Coming Soon]"
    )
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

def leaderboard(update, context):
    if not users:
        update.message.reply_text("No trainers yet!")
        return

    sorted_users = sorted(users.items(), key=lambda x: (-x[1]["level"], -x[1]["xp"]))
    msg = "* MegaGrok Leaderboard*"
    for i, (uid, data) in enumerate(sorted_users[:10], start=1):
        msg += f"{i}. Level {data['level']} | XP {data['xp']}"
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

updater = Updater(TOKEN)
dp = updater.dispatcher
dp.add_handler(CommandHandler("growmygrok", grow))
dp.add_handler(CommandHandler("mygrok", mygrok))
dp.add_handler(CommandHandler("leaderboard", leaderboard))

updater.start_polling()
updater.idle()
