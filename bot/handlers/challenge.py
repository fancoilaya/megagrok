# bot/handlers/challenge.py
# Telegram UI handler for Challenge Mode (Turn-based PvP)

from telebot import TeleBot, types
import time

from services.challenge_session import (
    create_challenge,
    accept_challenge,
    decline_challenge,
    attack,
    defend,
    end_turn,
    tick,
    USER_TO_SESSION,
    SESSIONS,
)

import bot.db as db

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

ONLINE_WINDOW = 180  # seconds considered "online"




# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def get_online_players(exclude_id: int):
    """
    Returns users active recently and not already in a challenge.
    """
    now = time.time()
    users = db.get_all_users()

    online = []
    for u in users:
        uid = u.get("id")
        if not uid or uid == exclude_id:
            continue
        if uid in USER_TO_SESSION:
            continue
        if now - u.get("last_active", 0) <= ONLINE_WINDOW:
            online.append(u)

    return online


def send_turn_ui(session: dict):
    """
    Sends the turn UI to the active player.
    """
    tick()

    if session["state"] == "FINISHED":
        return

    player = session["turn_owner"]
    opponent = session["p2"] if player == session["p1"] else session["p1"]

    hp_self = max(0, session["hp"][player])
    hp_opp = max(0, session["hp"][opponent])
    seconds_left = max(0, int(session["turn_deadline"] - time.time()))

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⚔️ Attack", callback_data="challenge:attack"),
        types.InlineKeyboardButton("🛡️ Defend", callback_data="challenge:defend"),
    )

    bot.send_message(
        player,
        f"⚔️ *Your Turn*\n\n"
        f"❤️ You: {hp_self}\n"
        f"💀 Opponent: {hp_opp}\n\n"
        f"⏱️ {seconds_left}s remaining",
        reply_markup=kb,
        parse_mode="Markdown",
    )


def send_battle_end(session: dict):
    """
    Notify both players that the battle ended.
    """
    p1, p2 = session["p1"], session["p2"]
    hp1, hp2 = session["hp"][p1], session["hp"][p2]

    if hp1 > hp2:
        winner, loser = p1, p2
    else:
        winner, loser = p2, p1

    bot.send_message(winner, "🏆 *You won the duel!*", parse_mode="Markdown")
    bot.send_message(loser, "💀 *You lost the duel.*", parse_mode="Markdown")


# -------------------------------------------------------------------
# COMMANDS
# -------------------------------------------------------------------

@bot.message_handler(commands=["challenge"])
def challenge_menu(msg):
    tick()

    user_id = msg.from_user.id

    if user_id in USER_TO_SESSION:
        bot.reply_to(msg, "⚠️ You are already in a duel.")
        return

    players = get_online_players(user_id)

    if not players:
        bot.reply_to(msg, "😴 No players available to challenge right now.")
        return

    kb = types.InlineKeyboardMarkup()
    for p in players[:5]:
        kb.add(
            types.InlineKeyboardButton(
                f"{p.get('name','Player')} (Lv {p.get('level',1)})",
                callback_data=f"challenge:send:{p['id']}",
            )
        )

    bot.reply_to(
        msg,
        "⚔️ *Challenge an opponent*",
        reply_markup=kb,
        parse_mode="Markdown",
    )


# -------------------------------------------------------------------
# CALLBACKS
# -------------------------------------------------------------------

@bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:send:"))
def send_challenge(call):
    tick()

    challenger = call.from_user.id
    target = int(call.data.split(":")[2])

    try:
        session = create_challenge(challenger, target)
    except ValueError:
        bot.answer_callback_query(call.id, "Player unavailable.")
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(
            "Accept ⚔️", callback_data=f"challenge:accept:{session['id']}"
        ),
        types.InlineKeyboardButton(
            "Decline ❌", callback_data=f"challenge:decline:{session['id']}"
        ),
    )

    bot.send_message(
        target,
        f"⚠️ *Duel Challenge Received*\n\n"
        f"{call.from_user.first_name} challenges you.\n"
        f"⏱️ Respond within 30 seconds.",
        reply_markup=kb,
        parse_mode="Markdown",
    )

    bot.answer_callback_query(call.id, "Challenge sent ⚔️")


@bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:accept:"))
def accept_challenge_cb(call):
    tick()

    session_id = call.data.split(":")[2]
    ok = accept_challenge(session_id)

    if not ok:
        bot.answer_callback_query(call.id, "Challenge expired.")
        return

    session = SESSIONS.get(session_id)
    if not session:
        return

    send_turn_ui(session)


@bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:decline:"))
def decline_challenge_cb(call):
    session_id = call.data.split(":")[2]
    decline_challenge(session_id)
    bot.answer_callback_query(call.id, "Challenge declined.")


@bot.callback_query_handler(func=lambda c: c.data == "challenge:attack")
def challenge_attack(call):
    tick()

    user_id = call.from_user.id
    session_id = USER_TO_SESSION.get(user_id)
    if not session_id:
        return

    session = SESSIONS.get(session_id)
    if not session:
        return

    if attack(session, user_id):
        end_turn(session)

        if session["state"] == "FINISHED":
            send_battle_end(session)
        else:
            send_turn_ui(session)


@bot.callback_query_handler(func=lambda c: c.data == "challenge:defend")
def challenge_defend(call):
    tick()

    user_id = call.from_user.id
    session_id = USER_TO_SESSION.get(user_id)
    if not session_id:
        return

    session = SESSIONS.get(session_id)
    if not session:
        return

    if defend(session, user_id):
        end_turn(session)

        if session["state"] == "FINISHED":
            send_battle_end(session)
        else:
            send_turn_ui(session)
