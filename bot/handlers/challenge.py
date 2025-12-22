# bot/handlers/challenge.py
# Challenge Mode — Turn-based PvP (Online-only, stable)

import time
from telebot import TeleBot, types

import bot.db as db

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

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

ONLINE_WINDOW = 300  # 5 minutes


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def get_online_players(exclude_id: int):
    now = int(time.time())
    users = db.get_all_users()

    online = []
    for u in users:
        uid = u.get("id") or u.get("user_id")
        if not uid or uid == exclude_id:
            continue

        # Skip users already in a duel
        if uid in USER_TO_SESSION:
            continue

        # Skip inactive users
        last_active = int(u.get("last_active", 0))
        if now - last_active > ONLINE_WINDOW:
            continue

        # Skip shielded users (if applicable)
        if u.get("pvp_shield_until", 0) > now:
            continue

        online.append(u)

    return online


def render_turn_text(session: dict, player: int):
    opponent = session["p2"] if player == session["p1"] else session["p1"]
    hp_self = max(0, session["hp"][player])
    hp_opp = max(0, session["hp"][opponent])
    seconds_left = max(0, int(session["turn_deadline"] - time.time()))

    return (
        "⚔️ <b>Your Turn</b>\n\n"
        f"❤️ You: <b>{hp_self}</b>\n"
        f"💀 Opponent: <b>{hp_opp}</b>\n\n"
        f"⏱️ <b>{seconds_left}s</b> remaining"
    )


def render_turn_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⚔️ Attack", callback_data="challenge:attack"),
        types.InlineKeyboardButton("🛡️ Defend", callback_data="challenge:defend"),
    )
    return kb


# -------------------------------------------------------------------
# HANDLER SETUP
# -------------------------------------------------------------------

def setup(bot: TeleBot):

    # ---------------------------------------------------------------
    # /challenge command
    # ---------------------------------------------------------------
    @bot.message_handler(commands=["challenge"])
    def challenge_menu(message):
        tick()

        uid = message.from_user.id
        db.touch_last_active(uid)

        if uid in USER_TO_SESSION:
            bot.reply_to(message, "⚠️ You are already in a duel.")
            return

        players = get_online_players(uid)

        if not players:
            bot.reply_to(message, "😴 No players available to challenge right now.")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for p in players[:5]:
            pid = p.get("id") or p.get("user_id")
            name = p.get("name") or p.get("username") or f"User{pid}"
            level = p.get("level", 1)

            kb.add(
                types.InlineKeyboardButton(
                    f"⚔️ {name} (Lv {level})",
                    callback_data=f"challenge:send:{pid}",
                )
            )

        bot.send_message(
            message.chat.id,
            "⚔️ <b>Challenge an online opponent</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )

    # ---------------------------------------------------------------
    # Send challenge
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:send:"))
    def send_challenge(call):
        tick()

        challenger = call.from_user.id
        db.touch_last_active(challenger)

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
            "⚠️ <b>Duel Challenge Received</b>\n\n"
            f"{call.from_user.first_name} challenges you.\n"
            "⏱️ Respond within <b>30 seconds</b>.",
            reply_markup=kb,
            parse_mode="HTML",
        )

        bot.answer_callback_query(call.id, "Challenge sent ⚔️")

    # ---------------------------------------------------------------
    # Accept / Decline
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:accept:"))
    def accept_cb(call):
        tick()

        uid = call.from_user.id
        db.touch_last_active(uid)

        session_id = call.data.split(":")[2]
        if not accept_challenge(session_id):
            bot.answer_callback_query(call.id, "Challenge expired.")
            return

        session = SESSIONS.get(session_id)
        if not session:
            return

        player = session["turn_owner"]
        bot.send_message(
            player,
            render_turn_text(session, player),
            reply_markup=render_turn_kb(),
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("challenge:decline:"))
    def decline_cb(call):
        tick()
        db.touch_last_active(call.from_user.id)

        decline_challenge(call.data.split(":")[2])
        bot.answer_callback_query(call.id, "Challenge declined.")

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "challenge:attack")
    def attack_cb(call):
        tick()

        uid = call.from_user.id
        db.touch_last_active(uid)

        session_id = USER_TO_SESSION.get(uid)
        if not session_id:
            return

        session = SESSIONS.get(session_id)
        if not session:
            return

        if attack(session, uid):
            end_turn(session)

        if session["state"] == "FINISHED":
            bot.send_message(uid, "🏆 <b>You won the duel!</b>", parse_mode="HTML")
        else:
            player = session["turn_owner"]
            bot.send_message(
                player,
                render_turn_text(session, player),
                reply_markup=render_turn_kb(),
                parse_mode="HTML",
            )

    @bot.callback_query_handler(func=lambda c: c.data == "challenge:defend")
    def defend_cb(call):
        tick()

        uid = call.from_user.id
        db.touch_last_active(uid)

        session_id = USER_TO_SESSION.get(uid)
        if not session_id:
            return

        session = SESSIONS.get(session_id)
        if not session:
            return

        if defend(session, uid):
            end_turn(session)

        if session["state"] == "FINISHED":
            bot.send_message(uid, "🏆 <b>You won the duel!</b>", parse_mode="HTML")
        else:
            player = session["turn_owner"]
            bot.send_message(
                player,
                render_turn_text(session, player),
                reply_markup=render_turn_kb(),
                parse_mode="HTML",
            )
