"""
╔══════════════════════════════════════════════════════════════╗
║         PREMIUM ECONOMY BOT — single file edition            ║
║                  (JSON storage, no MongoDB)                  ║
╚══════════════════════════════════════════════════════════════╝

SETUP:
  pip install python-telegram-bot==20.7 deep-translator gTTS
  Set BOT_TOKEN, ADMIN_IDS, CONTACT_ADMIN below, then run:  python bot.py
"""

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
BOT_TOKEN              = "8825222927:AAH90I76dkml6D7u4EH3Lp6EouHWOvh9VV8"
ADMIN_IDS              = [7121570824]
CONTACT_ADMIN_USERNAME = "ITACHIXERAA"
DAILY_COINS            = 500
DAILY_GEMS             = 2
CLAIM_BONUS            = 10_000
BOT_NAME               = "ᴘʀᴇᴍɪᴜᴍ ʙᴏᴛ"
DATA_FILE              = "bot_data.json"

# ══════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════
import os, json, random, asyncio, logging, io, tempfile
from datetime import datetime, date

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      BotCommand, ChatPermissions)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          filters, CallbackQueryHandler, ContextTypes)
from telegram.constants import ParseMode, ChatMemberStatus

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("premiumbot")

# ══════════════════════════════════════════════════════════════
#  JSON “DATABASE”
# ══════════════════════════════════════════════════════════════
_DEFAULT_DB = {
    "users": {},        # uid -> {coins, gems, wallet, kills, daily, claimed, items, emoji, protected, banned, name}
    "groups": {},       # gid -> {open: bool, title}
    "coupons": {},      # code -> {coins, gems, uses, used_by:[]}
    "bomb_scores": {},  # uid -> wins
    "stats": {"started": 0, "commands": 0},
}

def _load():
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(_DEFAULT_DB))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        for k, v in _DEFAULT_DB.items():
            db.setdefault(k, v if not isinstance(v, dict) else {})
        return db
    except Exception:
        return json.loads(json.dumps(_DEFAULT_DB))

def _save():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)

DB = _load()

def U(uid, name=""):
    uid = str(uid)
    u = DB["users"].get(uid)
    if not u:
        u = {"coins": 1000, "gems": 0, "wallet": 0, "kills": 0,
             "daily": "", "claimed": False, "items": [], "emoji": "✨",
             "protected": 0, "banned": False, "name": name or "User"}
        DB["users"][uid] = u
    if name:
        u["name"] = name
    return u

def G(gid, title=""):
    gid = str(gid)
    g = DB["groups"].get(gid)
    if not g:
        g = {"open": True, "title": title}
        DB["groups"][gid] = g
    if title:
        g["title"] = title
    return g

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def mention(user):
    name = (user.full_name or "User").replace("<", "").replace(">", "")
    return f'<a href="tg://user?id={user.id}">{name}</a>'

def fmt(n):
    return f"{int(n):,}"

def replied(update: Update):
    return update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else None

def is_admin(uid):
    return uid in ADMIN_IDS

def gate_group_open(update: Update):
    if update.effective_chat.type in ("group", "supergroup"):
        g = G(update.effective_chat.id, update.effective_chat.title or "")
        return g["open"]
    return True

async def is_chat_admin(update, context, uid):
    try:
        m = await context.bot.get_chat_member(update.effective_chat.id, uid)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False

def kb(rows):
    """rows: list[list[(text, callback_data or url=...)]]"""
    out = []
    for row in rows:
        line = []
        for item in row:
            if len(item) == 3 and item[2] == "url":
                line.append(InlineKeyboardButton(item[0], url=item[1]))
            else:
                line.append(InlineKeyboardButton(item[0], callback_data=item[1]))
        out.append(line)
    return InlineKeyboardMarkup(out)

async def safe_reply(update, text, **kw):
    kw.setdefault("parse_mode", ParseMode.HTML)
    kw.setdefault("disable_web_page_preview", True)
    return await update.effective_message.reply_text(text, **kw)

async def track(update):
    DB["stats"]["commands"] = DB["stats"].get("commands", 0) + 1
    if update.effective_user:
        U(update.effective_user.id, update.effective_user.full_name)
    if update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
        G(update.effective_chat.id, update.effective_chat.title or "")
    _save()

# ══════════════════════════════════════════════════════════════
#  /start  /help  /pay
# ══════════════════════════════════════════════════════════════
WELCOME = (
    "🎀 <b>Welcome to {bot}</b> 🎀\n\n"
    "💎 Economy • 🎮 Games • 💞 Fun Replies • 🛡 Protection\n"
    "Type /economy /game /coupons to explore!\n\n"
    "👑 Owner: @{owner}"
)

async def cmd_start(update, context):
    await track(update)
    DB["stats"]["started"] = DB["stats"].get("started", 0) + 1
    buttons = kb([
        [("➕ Add Me To Group", f"https://t.me/{context.bot.username}?startgroup=true", "url")],
        [("💎 Economy", "menu:eco"), ("🎮 Games", "menu:game")],
        [("🎁 Coupons", "menu:cpn"), ("❓ Help", "menu:help")],
        [("👑 Contact Owner", f"https://t.me/{CONTACT_ADMIN_USERNAME}", "url")],
    ])
    await safe_reply(update,
        WELCOME.format(bot=BOT_NAME, owner=CONTACT_ADMIN_USERNAME),
        reply_markup=buttons)

async def cmd_help(update, context):
    await track(update)
    txt = (
        "🛠 <b>Admin / Owner Commands</b>\n\n"
        "👮 /ban /unban  — moderate users\n"
        "📢 /broadcast  — message all users\n"
        "📊 /stats       — bot statistics\n"
        "🎟 /addcoupon CODE coins gems uses\n"
        "🔓 /open  /close — toggle gaming commands\n"
    )
    await safe_reply(update, txt)

async def cmd_pay(update, context):
    await track(update)
    btn = kb([
        [("💎 1 Month — $4.99", f"https://t.me/{CONTACT_ADMIN_USERNAME}", "url")],
        [("💎 3 Months — $11.99", f"https://t.me/{CONTACT_ADMIN_USERNAME}", "url")],
        [("💎 Lifetime — $29.99", f"https://t.me/{CONTACT_ADMIN_USERNAME}", "url")],
    ])
    await safe_reply(update,
        f"💳 <b>Buy Premium for {BOT_NAME}</b>\n\n"
        "Unlock exclusive perks, bigger daily rewards, and premium-only games.\n"
        f"Contact @{CONTACT_ADMIN_USERNAME} to purchase.",
        reply_markup=btn)

# ══════════════════════════════════════════════════════════════
#  /economy /game /coupons /own  menus
# ══════════════════════════════════════════════════════════════
async def cmd_economy(update, context):
    await track(update)
    txt = (
        "💎 <b>Global Economy Commands</b>\n\n"
        "💰 /bal — check balance\n"
        "🎁 /daily — claim daily cash\n"
        "💠 /gems — check gems\n"
        "🔐 /wallet — secure wallet\n"
        "🛡 /protect — robbery shield\n"
        "🤝 /give — give money (reply)\n"
        "🗡 /rob — rob someone (reply)\n"
        "🏆 /toprich — top 10 richest\n"
        "💀 /topkill — top 10 killers\n"
        "🎒 /items — list items\n"
        "🛒 /item — buy/use item\n"
        "🎁 /gift — gift an item\n"
        "📈 /rank — your rank\n"
    )
    await safe_reply(update, txt)

async def cmd_game(update, context):
    await track(update)
    txt = (
        "🎮 <b>Mini-Games</b>\n\n"
        "💣 /bomb — bomb game\n"
        "🃏 /card — card game\n"
        "🎭 /bluff — bluff game\n"
        "💻 /hack — hackers game\n"
        "❓ /truth — pick a truth\n"
        "🎯 /dare — pick a dare\n"
        "🧩 /puzzle — pick a puzzle\n"
        "🏅 /leaders — bomb leaders\n"
    )
    await safe_reply(update, txt)

async def cmd_coupons(update, context):
    await track(update)
    txt = (
        "🎟 <b>Coupon Commands</b>\n\n"
        "🎫 /redeem CODE — redeem a coupon\n"
        "👑 Admin:\n"
        "   /addcoupon CODE coins gems uses\n"
        "   /delcoupon CODE\n"
        "   /coupons_list\n"
    )
    await safe_reply(update, txt)

async def cmd_own(update, context):
    await track(update)
    await safe_reply(update,
        "🖼 <b>Make Your Own Sticker Pack</b>\n\n"
        "Send me a static or animated sticker and reply with /own pack_name\n"
        "I'll add it to a pack named <code>pack_name_by_{u}</code> on Telegram."
        .format(u=context.bot.username))

# ══════════════════════════════════════════════════════════════
#  /open  /close  (gaming gate)
# ══════════════════════════════════════════════════════════════
async def cmd_open(update, context):
    await track(update)
    if update.effective_chat.type not in ("group", "supergroup"):
        return await safe_reply(update, "👥 Use this in a group.")
    if not await is_chat_admin(update, context, update.effective_user.id) and not is_admin(update.effective_user.id):
        return await safe_reply(update, "🚫 Admins only.")
    G(update.effective_chat.id, update.effective_chat.title or "")["open"] = True
    _save()
    await safe_reply(update, "🔓 <b>Gaming commands OPENED</b> in this group.")

async def cmd_close(update, context):
    await track(update)
    if update.effective_chat.type not in ("group", "supergroup"):
        return await safe_reply(update, "👥 Use this in a group.")
    if not await is_chat_admin(update, context, update.effective_user.id) and not is_admin(update.effective_user.id):
        return await safe_reply(update, "🚫 Admins only.")
    G(update.effective_chat.id, update.effective_chat.title or "")["open"] = False
    _save()
    await safe_reply(update, "🔒 <b>Gaming commands CLOSED</b> in this group.")

# ══════════════════════════════════════════════════════════════
#  ECONOMY: /bal /daily /gems /wallet /claim /protect /give /rob
# ══════════════════════════════════════════════════════════════
async def cmd_bal(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    u = U(target.id, target.full_name)
    txt = (
        f"💰 <b>{target.full_name}'s Balance</b>\n\n"
        f"💵 Cash:   <b>{fmt(u['coins'])}</b>\n"
        f"🔐 Wallet: <b>{fmt(u['wallet'])}</b>\n"
        f"💎 Gems:   <b>{fmt(u['gems'])}</b>\n"
        f"💀 Kills:  <b>{fmt(u['kills'])}</b>"
    )
    await safe_reply(update, txt)

async def cmd_daily(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    today = str(date.today())
    if u["daily"] == today:
        return await safe_reply(update, "⏳ You already claimed your daily reward. Come back tomorrow!")
    u["daily"] = today
    u["coins"] += DAILY_COINS
    u["gems"]  += DAILY_GEMS
    _save()
    await safe_reply(update,
        f"🎁 <b>Daily reward claimed!</b>\n"
        f"💵 +{fmt(DAILY_COINS)} coins\n"
        f"💎 +{DAILY_GEMS} gems")

async def cmd_gems(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    await safe_reply(update, f"💎 You have <b>{fmt(u['gems'])}</b> gems.")

async def cmd_wallet(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    args = context.args or []
    if not args:
        return await safe_reply(update,
            f"🔐 <b>Wallet</b>\nIn wallet: <b>{fmt(u['wallet'])}</b>\nUse: <code>/wallet deposit 500</code> or <code>/wallet withdraw 500</code>")
    if len(args) < 2:
        return await safe_reply(update, "Usage: /wallet deposit|withdraw &lt;amount&gt;")
    op, amt = args[0].lower(), args[1]
    try:
        amt = int(amt)
    except ValueError:
        return await safe_reply(update, "❌ Invalid amount.")
    if amt <= 0:
        return await safe_reply(update, "❌ Amount must be positive.")
    if op == "deposit":
        if u["coins"] < amt:
            return await safe_reply(update, "❌ Not enough cash.")
        u["coins"] -= amt; u["wallet"] += amt
    elif op == "withdraw":
        if u["wallet"] < amt:
            return await safe_reply(update, "❌ Not enough in wallet.")
        u["wallet"] -= amt; u["coins"] += amt
    else:
        return await safe_reply(update, "❌ Use deposit or withdraw.")
    _save()
    await safe_reply(update, f"✅ Done. Cash: {fmt(u['coins'])} | Wallet: {fmt(u['wallet'])}")

async def cmd_claim(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    if u.get("claimed"):
        return await safe_reply(update, "✅ You already claimed your group bonus.")
    if update.effective_chat.type not in ("group", "supergroup"):
        return await safe_reply(update, "👥 Add me to a group and run /claim there to get your bonus!")
    u["claimed"] = True
    u["coins"] += CLAIM_BONUS
    _save()
    await safe_reply(update, f"🎉 +{fmt(CLAIM_BONUS)} cash credited for adding me to a group!")

async def cmd_protect(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    COST = 2000
    if u["coins"] < COST:
        return await safe_reply(update, f"❌ Protection costs {fmt(COST)} cash.")
    u["coins"] -= COST
    u["protected"] = u.get("protected", 0) + 5
    _save()
    await safe_reply(update, f"🛡 Protection activated for next <b>{u['protected']}</b> robbery attempts.")

async def cmd_give(update, context):
    await track(update)
    target = replied(update)
    if not target:
        return await safe_reply(update, "↩️ Reply to a user to give cash.")
    if not context.args:
        return await safe_reply(update, "Usage: reply + /give &lt;amount&gt;")
    try:
        amt = int(context.args[0])
    except ValueError:
        return await safe_reply(update, "❌ Invalid amount.")
    u = U(update.effective_user.id, update.effective_user.full_name)
    if amt <= 0 or u["coins"] < amt:
        return await safe_reply(update, "❌ Not enough cash.")
    t = U(target.id, target.full_name)
    u["coins"] -= amt; t["coins"] += amt
    _save()
    await safe_reply(update, f"🤝 {mention(update.effective_user)} gave <b>{fmt(amt)}</b> to {mention(target)}")

async def cmd_rob(update, context):
    await track(update)
    target = replied(update)
    if not target:
        return await safe_reply(update, "↩️ Reply to a user to rob them.")
    if target.id == update.effective_user.id:
        return await safe_reply(update, "🤨 You can't rob yourself.")
    t = U(target.id, target.full_name)
    u = U(update.effective_user.id, update.effective_user.full_name)
    if t.get("protected", 0) > 0:
        t["protected"] -= 1
        _save()
        return await safe_reply(update, f"🛡 {mention(target)} is protected! Robbery failed.")
    if t["coins"] < 100:
        return await safe_reply(update, "💸 Target has nothing worth stealing.")
    if random.random() < 0.5:
        steal = random.randint(50, min(2000, t["coins"]))
        t["coins"] -= steal; u["coins"] += steal
        _save()
        await safe_reply(update, f"🗡 {mention(update.effective_user)} robbed <b>{fmt(steal)}</b> from {mention(target)}!")
    else:
        fine = random.randint(100, 500)
        u["coins"] = max(0, u["coins"] - fine)
        _save()
        await safe_reply(update, f"🚨 Caught! {mention(update.effective_user)} paid a fine of <b>{fmt(fine)}</b>.")

# ══════════════════════════════════════════════════════════════
#  /toprich /topkill /rank /leaders
# ══════════════════════════════════════════════════════════════
def _top(field, n=10):
    arr = [(uid, u) for uid, u in DB["users"].items()]
    arr.sort(key=lambda x: x[1].get(field, 0), reverse=True)
    return arr[:n]

async def cmd_toprich(update, context):
    await track(update)
    lines = ["🏆 <b>Top 10 Richest</b>\n"]
    for i, (uid, u) in enumerate(_top("coins"), 1):
        medal = "🥇🥈🥉"[i-1] if i <= 3 else f"  {i}."
        lines.append(f"{medal} {u['name']} — 💵 {fmt(u['coins'] + u['wallet'])}")
    await safe_reply(update, "\n".join(lines))

async def cmd_topkill(update, context):
    await track(update)
    lines = ["💀 <b>Top 10 Killers</b>\n"]
    for i, (uid, u) in enumerate(_top("kills"), 1):
        medal = "🥇🥈🥉"[i-1] if i <= 3 else f"  {i}."
        lines.append(f"{medal} {u['name']} — 🗡 {fmt(u['kills'])}")
    await safe_reply(update, "\n".join(lines))

async def cmd_rank(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    arr = _top("coins", 9999)
    pos = next((i+1 for i, (uid, _) in enumerate(arr) if uid == str(target.id)), len(arr))
    u = U(target.id, target.full_name)
    await safe_reply(update,
        f"📈 <b>{target.full_name}</b>\n"
        f"🏆 Rank: <b>#{pos}</b>\n"
        f"💵 Net worth: <b>{fmt(u['coins'] + u['wallet'])}</b>\n"
        f"💀 Kills: <b>{fmt(u['kills'])}</b>")

async def cmd_leaders(update, context):
    await track(update)
    arr = sorted(DB["bomb_scores"].items(), key=lambda x: x[1], reverse=True)[:10]
    if not arr:
        return await safe_reply(update, "🏅 No bomb leaders yet. Play /bomb!")
    lines = ["💣 <b>Bomb Game Top Leaders</b>\n"]
    for i, (uid, wins) in enumerate(arr, 1):
        u = DB["users"].get(uid, {"name": "User"})
        medal = "🥇🥈🥉"[i-1] if i <= 3 else f"  {i}."
        lines.append(f"{medal} {u['name']} — 🏆 {wins} wins")
    await safe_reply(update, "\n".join(lines))

# ══════════════════════════════════════════════════════════════
#  ITEMS
# ══════════════════════════════════════════════════════════════
ITEMS = {
    "shield":  {"emoji": "🛡", "price": 2500, "desc": "Adds 5 protection charges."},
    "bomb":    {"emoji": "💣", "price": 1500, "desc": "Use to kill another user (reply)."},
    "potion":  {"emoji": "🧪", "price": 800,  "desc": "Heals/revives a fallen user (reply)."},
    "rose":    {"emoji": "🌹", "price": 300,  "desc": "Give to your crush."},
    "crown":   {"emoji": "👑", "price": 9999, "desc": "Pure flex. Wear a crown."},
}

async def cmd_items(update, context):
    await track(update)
    lines = ["🎒 <b>Available Items</b>\n"]
    for name, it in ITEMS.items():
        lines.append(f"{it['emoji']} <b>{name}</b> — 💵 {fmt(it['price'])}\n   <i>{it['desc']}</i>")
    lines.append("\nBuy: <code>/item buy NAME</code>  •  Use: <code>/item use NAME</code>  •  Inv: <code>/item</code>")
    await safe_reply(update, "\n".join(lines))

async def cmd_item(update, context):
    await track(update)
    u = U(update.effective_user.id, update.effective_user.full_name)
    if not context.args:
        if not u["items"]:
            return await safe_reply(update, "🎒 Your inventory is empty. See /items.")
        counts = {}
        for it in u["items"]:
            counts[it] = counts.get(it, 0) + 1
        lines = ["🎒 <b>Your Inventory</b>\n"]
        for name, c in counts.items():
            em = ITEMS.get(name, {}).get("emoji", "📦")
            lines.append(f"{em} {name} ×{c}")
        return await safe_reply(update, "\n".join(lines))
    op = context.args[0].lower()
    name = (context.args[1] if len(context.args) > 1 else "").lower()
    if op == "buy":
        if name not in ITEMS:
            return await safe_reply(update, "❌ Unknown item.")
        it = ITEMS[name]
        if u["coins"] < it["price"]:
            return await safe_reply(update, "❌ Not enough cash.")
        u["coins"] -= it["price"]; u["items"].append(name)
        _save()
        return await safe_reply(update, f"🛒 Bought {it['emoji']} <b>{name}</b>!")
    if op == "use":
        if name not in u["items"]:
            return await safe_reply(update, "❌ You don't own that item.")
        u["items"].remove(name)
        target = replied(update)
        if name == "shield":
            u["protected"] = u.get("protected", 0) + 5
            msg = "🛡 +5 protection charges!"
        elif name == "bomb" and target:
            t = U(target.id, target.full_name)
            t["coins"] = max(0, t["coins"] - 1000)
            u["kills"] = u.get("kills", 0) + 1
            msg = f"💣 You bombed {mention(target)}! −1,000 cash, +1 kill."
        elif name == "potion" and target:
            t = U(target.id, target.full_name)
            t["coins"] += 500
            msg = f"🧪 Revived {mention(target)} with +500 cash."
        elif name == "rose" and target:
            msg = f"🌹 You gave a rose to {mention(target)} 💕"
        elif name == "crown":
            u["emoji"] = "👑"
            msg = "👑 You're wearing the crown!"
        else:
            u["items"].append(name)
            return await safe_reply(update, "↩️ Reply to a user to use this item.")
        _save()
        return await safe_reply(update, msg)
    await safe_reply(update, "Usage: /item buy NAME  •  /item use NAME")

async def cmd_gift(update, context):
    await track(update)
    target = replied(update)
    if not target or not context.args:
        return await safe_reply(update, "↩️ Reply to a user + <code>/gift item_name</code>")
    name = context.args[0].lower()
    u = U(update.effective_user.id, update.effective_user.full_name)
    if name not in u["items"]:
        return await safe_reply(update, "❌ You don't own that item.")
    u["items"].remove(name)
    t = U(target.id, target.full_name)
    t["items"].append(name)
    _save()
    em = ITEMS.get(name, {}).get("emoji", "🎁")
    await safe_reply(update, f"🎁 {mention(update.effective_user)} gifted {em} <b>{name}</b> to {mention(target)}")

# ══════════════════════════════════════════════════════════════
#  GAMES: /bomb /bluff /card /hack
# ══════════════════════════════════════════════════════════════
def gating(handler):
    async def inner(update, context):
        if not gate_group_open(update):
            return await safe_reply(update, "🔒 Gaming commands are closed in this group. Admins: /open")
        return await handler(update, context)
    return inner

@gating
async def cmd_bomb(update, context):
    await track(update)
    n = random.randint(1, 6)
    pick = random.randint(1, 6)
    rows = [[(f"💣 {i}", f"bomb:{i}:{n}") for i in range(1, 4)],
            [(f"💣 {i}", f"bomb:{i}:{n}") for i in range(4, 7)]]
    await safe_reply(update,
        f"💣 <b>Bomb Game</b>\nPick a number 1–6. One of them is the bomb!",
        reply_markup=kb(rows))

async def cb_bomb(update, context):
    q = update.callback_query
    await q.answer()
    _, pick, bomb = q.data.split(":")
    pick, bomb = int(pick), int(bomb)
    u = U(q.from_user.id, q.from_user.full_name)
    if pick == bomb:
        u["coins"] = max(0, u["coins"] - 500)
        await q.edit_message_text(f"💥 BOOM! Bomb was {bomb}. {q.from_user.full_name} loses 500 cash.")
    else:
        u["coins"] += 750
        DB["bomb_scores"][str(q.from_user.id)] = DB["bomb_scores"].get(str(q.from_user.id), 0) + 1
        await q.edit_message_text(f"🎉 Safe! Bomb was {bomb}. {q.from_user.full_name} wins 750 cash.")
    _save()

@gating
async def cmd_bluff(update, context):
    await track(update)
    truths = ["I never lose at this game.", "I have a secret stash of 1M coins.",
              "I once robbed an admin.", "I cried during a Pixar movie."]
    await safe_reply(update,
        f"🎭 <b>Bluff Game</b>\nStatement: <i>{random.choice(truths)}</i>",
        reply_markup=kb([[("🤥 Bluff", "bluff:b"), ("✅ Truth", "bluff:t")]]))

async def cb_bluff(update, context):
    q = update.callback_query
    await q.answer()
    verdict = random.choice(["bluff", "truth"])
    pick = "bluff" if q.data.endswith("b") else "truth"
    u = U(q.from_user.id, q.from_user.full_name)
    if pick == verdict:
        u["coins"] += 300
        await q.edit_message_text(f"✅ Correct! It was a {verdict}. +300 cash.")
    else:
        u["coins"] = max(0, u["coins"] - 200)
        await q.edit_message_text(f"❌ Wrong! It was a {verdict}. −200 cash.")
    _save()

@gating
async def cmd_card(update, context):
    await track(update)
    your, bot_c = random.randint(1, 13), random.randint(1, 13)
    u = U(update.effective_user.id, update.effective_user.full_name)
    res = "🤝 Tie" if your == bot_c else ("🏆 You win! +400" if your > bot_c else "💀 You lose! −200")
    if your > bot_c: u["coins"] += 400
    elif your < bot_c: u["coins"] = max(0, u["coins"] - 200)
    _save()
    await safe_reply(update, f"🃏 You: <b>{your}</b>  •  Bot: <b>{bot_c}</b>\n{res}")

@gating
async def cmd_hack(update, context):
    await track(update)
    pin = random.randint(1000, 9999)
    secret = random.randint(1000, 9999)
    u = U(update.effective_user.id, update.effective_user.full_name)
    if abs(pin - secret) < 500:
        u["coins"] += 1500
        msg = f"💻 PIN {pin} accepted! Hacked the mainframe! +1500"
    else:
        u["coins"] = max(0, u["coins"] - 300)
        msg = f"🚨 Wrong PIN {pin}. Trace started. −300"
    _save()
    await safe_reply(update, msg)

# ══════════════════════════════════════════════════════════════
#  /truth /dare /puzzle
# ══════════════════════════════════════════════════════════════
TRUTHS = ["What's your biggest secret?", "Have you ever lied to a best friend?",
          "What's the most embarrassing thing you've done?",
          "Who do you have a crush on right now?",
          "What's the longest you've gone without showering?"]
DARES  = ["Send a selfie right now.", "Voice-message a love song.",
          "Change your name to '🐸 Frog' for an hour.",
          "DM your crush a random emoji.", "Speak in rhyme for 5 minutes."]
PUZZLES= [("I speak without a mouth and hear without ears. What am I?", "echo"),
          ("The more you take, the more you leave behind. What am I?", "footsteps"),
          ("What has keys but can't open locks?", "piano")]

async def cmd_truth(update, context):
    await track(update); await safe_reply(update, f"❓ <b>Truth</b>\n{random.choice(TRUTHS)}")
async def cmd_dare(update, context):
    await track(update); await safe_reply(update, f"🎯 <b>Dare</b>\n{random.choice(DARES)}")
async def cmd_puzzle(update, context):
    await track(update)
    q, a = random.choice(PUZZLES)
    await safe_reply(update, f"🧩 <b>Puzzle</b>\n{q}\n\n<tg-spoiler>Answer: {a}</tg-spoiler>")

# ══════════════════════════════════════════════════════════════
#  FUN REPLY COMMANDS
# ══════════════════════════════════════════════════════════════
FUN = {
    "crush":  ("💘", ["has a massive crush on", "secretly loves", "is blushing for"]),
    "love":   ("❤️", ["sends infinite love to", "wrote a poem for"]),
    "hug":    ("🤗", ["gives a warm hug to", "squeezes tightly"]),
    "kiss":   ("😘", ["plants a kiss on", "blows a kiss to"]),
    "bite":   ("🦷", ["bites", "nibbles on"]),
    "slap":   ("👋", ["slaps", "smacks"]),
    "punch":  ("👊", ["punches", "throws a haymaker at"]),
    "murder": ("🔪", ["murders", "ends the existence of"]),
    "look":   ("👀", ["rates the looks of", "checks out"]),
    "brain":  ("🧠", ["measures the IQ of", "scans the brain of"]),
}
async def fun_handler(update, context, key):
    await track(update)
    target = replied(update)
    if not target:
        return await safe_reply(update, "↩️ Reply to a user.")
    em, verbs = FUN[key]
    extra = ""
    if key == "look":   extra = f"\n💯 Rating: <b>{random.randint(1, 10)}/10</b>"
    elif key == "brain":extra = f"\n🧠 IQ: <b>{random.randint(40, 180)}</b>"
    await safe_reply(update,
        f"{em} {mention(update.effective_user)} {random.choice(verbs)} {mention(target)}{extra}")

def make_fun(k):
    async def h(update, context): await fun_handler(update, context, k)
    return h

async def cmd_stupid(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    await safe_reply(update, f"🤪 {mention(target)} stupidity meter: <b>{random.randint(0,100)}%</b>")

# ══════════════════════════════════════════════════════════════
#  /murder /kill /revive
# ══════════════════════════════════════════════════════════════
async def cmd_kill(update, context):
    await track(update)
    target = replied(update)
    if not target:
        return await safe_reply(update, "↩️ Reply to a user to kill them (in-game).")
    u = U(update.effective_user.id, update.effective_user.full_name)
    t = U(target.id, target.full_name)
    if t.get("protected", 0) > 0:
        t["protected"] -= 1; _save()
        return await safe_reply(update, f"🛡 {mention(target)} survived behind a shield!")
    u["kills"] = u.get("kills", 0) + 1
    t["coins"] = max(0, t["coins"] - 250)
    _save()
    await safe_reply(update, f"🔪 {mention(update.effective_user)} killed {mention(target)}! 💀")

async def cmd_revive(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    t = U(target.id, target.full_name)
    t["coins"] += 250
    _save()
    await safe_reply(update, f"💖 {mention(target)} has been revived!")

# ══════════════════════════════════════════════════════════════
#  /couples
# ══════════════════════════════════════════════════════════════
RECENT_USERS = {}  # chat_id -> list of (uid, name)
async def cmd_couples(update, context):
    await track(update)
    arr = RECENT_USERS.get(update.effective_chat.id, [])
    if len(arr) < 2:
        return await safe_reply(update, "💞 Not enough recent members to pick couples. Chat a bit and try again!")
    a, b = random.sample(arr, 2)
    await safe_reply(update, f"💞 <b>Today's Couple</b>\n💑 {a[1]}  ❤️  {b[1]}")

async def track_users(update, context):
    if update.effective_user and update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
        arr = RECENT_USERS.setdefault(update.effective_chat.id, [])
        entry = (update.effective_user.id, update.effective_user.full_name)
        if entry not in arr:
            arr.append(entry)
            if len(arr) > 40: arr.pop(0)

# ══════════════════════════════════════════════════════════════
#  /tr (translate) /voice
# ══════════════════════════════════════════════════════════════
async def cmd_tr(update, context):
    await track(update)
    try:
        from deep_translator import GoogleTranslator
    except Exception:
        return await safe_reply(update, "❌ Install: <code>pip install deep-translator</code>")
    args = context.args or []
    lang = "en"
    text = ""
    if args and len(args[0]) <= 5 and args[0].isalpha():
        lang = args[0]; text = " ".join(args[1:])
    else:
        text = " ".join(args)
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    if not text:
        return await safe_reply(update, "Usage: <code>/tr [lang] text</code> or reply to a message.")
    try:
        out = GoogleTranslator(source="auto", target=lang).translate(text)
        await safe_reply(update, f"🌐 <b>→ {lang}</b>\n{out}")
    except Exception as e:
        await safe_reply(update, f"❌ Translate error: {e}")

async def cmd_voice(update, context):
    await track(update)
    try:
        from gtts import gTTS
    except Exception:
        return await safe_reply(update, "❌ Install: <code>pip install gTTS</code>")
    text = " ".join(context.args) if context.args else (
        update.message.reply_to_message.text if update.message.reply_to_message else "")
    if not text:
        return await safe_reply(update, "Usage: <code>/voice text</code> or reply to a message.")
    try:
        tts = gTTS(text=text[:500], lang="en")
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            path = f.name
        tts.save(path)
        with open(path, "rb") as fp:
            await update.effective_message.reply_voice(voice=fp)
        os.remove(path)
    except Exception as e:
        await safe_reply(update, f"❌ Voice error: {e}")

# ══════════════════════════════════════════════════════════════
#  /detail /owner /admins /pfp /check /setemoji
# ══════════════════════════════════════════════════════════════
async def cmd_detail(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    await safe_reply(update,
        f"🪪 <b>User Details</b>\n"
        f"👤 Name: {target.full_name}\n"
        f"🆔 ID: <code>{target.id}</code>\n"
        f"🔗 Username: @{target.username if target.username else '—'}\n"
        f"🤖 Bot: {target.is_bot}\n"
        f"🌐 Language: {target.language_code or '—'}")

async def cmd_owner(update, context):
    await track(update)
    if update.effective_chat.type not in ("group", "supergroup"):
        return await safe_reply(update, "👥 Use this in a group.")
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        owner = next((a for a in admins if a.status == ChatMemberStatus.OWNER), None)
        if not owner:
            return await safe_reply(update, "👑 No owner found.")
        await safe_reply(update, f"👑 <b>Group Owner</b>\n{mention(owner.user)}")
    except Exception as e:
        await safe_reply(update, f"❌ {e}")

async def cmd_admins(update, context):
    await track(update)
    if update.effective_chat.type not in ("group", "supergroup"):
        return await safe_reply(update, "👥 Use this in a group.")
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        lines = ["👮 <b>Group Admins</b>\n"]
        for a in admins:
            crown = "👑 " if a.status == ChatMemberStatus.OWNER else "⭐ "
            lines.append(crown + mention(a.user))
        await safe_reply(update, "\n".join(lines))
    except Exception as e:
        await safe_reply(update, f"❌ {e}")

async def cmd_pfp(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    try:
        photos = await context.bot.get_user_profile_photos(target.id, limit=1)
        if photos.total_count == 0:
            return await safe_reply(update, "📷 No profile picture.")
        await update.effective_message.reply_photo(
            photos.photos[0][-1].file_id,
            caption=f"📷 {target.full_name}")
    except Exception as e:
        await safe_reply(update, f"❌ {e}")

async def cmd_check(update, context):
    await track(update)
    target = replied(update) or update.effective_user
    u = U(target.id, target.full_name)
    await safe_reply(update, f"✨ {target.full_name}'s emoji: <b>{u.get('emoji','✨')}</b>")

async def cmd_setemoji(update, context):
    await track(update)
    if not context.args:
        return await safe_reply(update, "Usage: <code>/setemoji 🔥</code>")
    e = context.args[0][:4]
    u = U(update.effective_user.id, update.effective_user.full_name)
    u["emoji"] = e; _save()
    await safe_reply(update, f"✅ Your emoji is now {e}")

# ══════════════════════════════════════════════════════════════
#  COUPONS
# ══════════════════════════════════════════════════════════════
async def cmd_redeem(update, context):
    await track(update)
    if not context.args:
        return await safe_reply(update, "Usage: <code>/redeem CODE</code>")
    code = context.args[0].upper()
    c = DB["coupons"].get(code)
    if not c:
        return await safe_reply(update, "❌ Invalid coupon.")
    if c["uses"] <= 0:
        return await safe_reply(update, "❌ Coupon expired.")
    uid = str(update.effective_user.id)
    if uid in c["used_by"]:
        return await safe_reply(update, "❌ You already used this coupon.")
    u = U(update.effective_user.id, update.effective_user.full_name)
    u["coins"] += c["coins"]; u["gems"] += c["gems"]
    c["uses"] -= 1; c["used_by"].append(uid)
    _save()
    await safe_reply(update, f"🎉 Redeemed! +{fmt(c['coins'])} cash, +{c['gems']} gems")

async def cmd_addcoupon(update, context):
    await track(update)
    if not is_admin(update.effective_user.id):
        return await safe_reply(update, "🚫 Owner only.")
    if len(context.args or []) < 4:
        return await safe_reply(update, "Usage: <code>/addcoupon CODE coins gems uses</code>")
    code, coins, gems, uses = context.args[0].upper(), int(context.args[1]), int(context.args[2]), int(context.args[3])
    DB["coupons"][code] = {"coins": coins, "gems": gems, "uses": uses, "used_by": []}
    _save()
    await safe_reply(update, f"✅ Coupon <code>{code}</code> created.")

async def cmd_delcoupon(update, context):
    await track(update)
    if not is_admin(update.effective_user.id): return
    if not context.args: return
    DB["coupons"].pop(context.args[0].upper(), None); _save()
    await safe_reply(update, "✅ Deleted.")

async def cmd_coupons_list(update, context):
    await track(update)
    if not is_admin(update.effective_user.id): return
    if not DB["coupons"]:
        return await safe_reply(update, "📭 No coupons.")
    lines = ["🎟 <b>Coupons</b>"]
    for c, v in DB["coupons"].items():
        lines.append(f"<code>{c}</code> — 💵{fmt(v['coins'])} 💎{v['gems']} • uses left: {v['uses']}")
    await safe_reply(update, "\n".join(lines))

# ══════════════════════════════════════════════════════════════
#  ADMIN: /broadcast /ban /unban /stats
# ══════════════════════════════════════════════════════════════
async def cmd_broadcast(update, context):
    await track(update)
    if not is_admin(update.effective_user.id):
        return await safe_reply(update, "🚫 Owner only.")
    text = " ".join(context.args)
    if not text:
        return await safe_reply(update, "Usage: <code>/broadcast message</code>")
    ok = fail = 0
    for uid in list(DB["users"].keys()):
        try:
            await context.bot.send_message(int(uid), f"📢 {text}")
            ok += 1
        except Exception:
            fail += 1
    await safe_reply(update, f"📢 Sent: {ok} • Failed: {fail}")

async def cmd_ban(update, context):
    await track(update)
    if not is_admin(update.effective_user.id):
        return await safe_reply(update, "🚫 Owner only.")
    target = replied(update)
    if not target:
        return await safe_reply(update, "↩️ Reply to a user.")
    U(target.id, target.full_name)["banned"] = True; _save()
    await safe_reply(update, f"🔨 Banned {mention(target)}")

async def cmd_unban(update, context):
    await track(update)
    if not is_admin(update.effective_user.id): return
    target = replied(update)
    if not target: return
    U(target.id, target.full_name)["banned"] = False; _save()
    await safe_reply(update, f"✅ Unbanned {mention(target)}")

async def cmd_stats(update, context):
    await track(update)
    await safe_reply(update,
        "📊 <b>Bot Stats</b>\n"
        f"👥 Users: <b>{len(DB['users'])}</b>\n"
        f"👨‍👩‍👧 Groups: <b>{len(DB['groups'])}</b>\n"
        f"🎟 Coupons: <b>{len(DB['coupons'])}</b>\n"
        f"🚀 Starts: <b>{DB['stats'].get('started',0)}</b>\n"
        f"⚙️ Commands run: <b>{DB['stats'].get('commands',0)}</b>")

# ══════════════════════════════════════════════════════════════
#  WELCOME on join + global ban gate
# ══════════════════════════════════════════════════════════════
async def on_new_members(update, context):
    for member in update.message.new_chat_members or []:
        if member.id == context.bot.id:
            await update.message.reply_text(
                f"🎀 Thanks for adding <b>{BOT_NAME}</b>!\nType /start to begin.",
                parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(
                f"👋 Welcome {mention(member)} to <b>{update.effective_chat.title}</b>!",
                parse_mode=ParseMode.HTML)

async def ban_gate(update, context):
    if update.effective_user:
        u = DB["users"].get(str(update.effective_user.id))
        if u and u.get("banned"):
            try:
                await safe_reply(update, "🔨 You are banned from using this bot.")
            except Exception:
                pass
            raise asyncio.CancelledError()

# ══════════════════════════════════════════════════════════════
#  MENU callback
# ══════════════════════════════════════════════════════════════
async def cb_menu(update, context):
    q = update.callback_query
    await q.answer()
    m = q.data.split(":")[1]
    routes = {
        "eco":  cmd_economy, "game": cmd_game,
        "cpn":  cmd_coupons, "help": cmd_help,
    }
    fake = Update(update.update_id, message=q.message)
    if m in routes:
        # call as if it were a command
        class Ctx: args = []
        try:
            await routes[m](Update(update.update_id, message=q.message), context)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
#  COMMAND MENU (Telegram’s slash-menu)
# ══════════════════════════════════════════════════════════════
COMMAND_MENU = [
    BotCommand("start",        "Talk to bot"),
    BotCommand("pay",          "Buy premium subscription"),
    BotCommand("gems",         "Check your gems"),
    BotCommand("daily",        "Claim free daily cash"),
    BotCommand("claim",        "Claim bonus for adding bot to groups"),
    BotCommand("coupons",      "Coupon commands"),
    BotCommand("economy",      "All economy commands"),
    BotCommand("game",         "All mini-games"),
    BotCommand("own",          "Make your own sticker pack"),
    BotCommand("help",         "Admin commands"),
    BotCommand("open",         "Open gaming commands"),
    BotCommand("close",        "Close gaming commands"),
    BotCommand("couples",      "Choose random couples"),
    BotCommand("crush",        "Reply to someone"),
    BotCommand("love",         "Reply to someone"),
    BotCommand("look",         "Rate someone's looks"),
    BotCommand("brain",        "Measure IQ"),
    BotCommand("stupid_meter", "Stupidity meter"),
    BotCommand("murder",       "Murder reply"),
    BotCommand("slap",         "Slap reply"),
    BotCommand("punch",        "Punch reply"),
    BotCommand("bite",         "Bite reply"),
    BotCommand("kiss",         "Kiss reply"),
    BotCommand("hug",          "Hug reply"),
    BotCommand("truth",        "Pick a truth"),
    BotCommand("dare",         "Pick a dare"),
    BotCommand("puzzle",       "Pick a puzzle"),
    BotCommand("tr",           "Translate any text"),
    BotCommand("detail",       "User details"),
    BotCommand("owner",        "Tag group owner"),
    BotCommand("admins",       "Show group admins"),
    BotCommand("bal",          "Check balance"),
    BotCommand("pfp",          "Check profile pic"),
    BotCommand("wallet",       "Save balance from robbery"),
    BotCommand("rob",          "Rob someone"),
    BotCommand("kill",         "Kill someone (in-game)"),
    BotCommand("revive",       "Revive someone"),
    BotCommand("protect",      "Protection from robbery"),
    BotCommand("give",         "Give money to replied user"),
    BotCommand("toprich",      "Top 10 richest"),
    BotCommand("topkill",      "Top 10 killers"),
    BotCommand("item",         "Buy/use items"),
    BotCommand("rank",         "Check rank"),
    BotCommand("leaders",      "Bomb game leaders"),
    BotCommand("items",        "All items"),
    BotCommand("bomb",         "Bomb game"),
    BotCommand("bluff",        "Bluff game"),
    BotCommand("card",         "Card game"),
    BotCommand("hack",         "Hackers game"),
    BotCommand("gift",         "Gift an item"),
    BotCommand("voice",        "Text to voice"),
    BotCommand("check",        "Check user emoji"),
    BotCommand("setemoji",     "Set your custom emoji"),
]

async def _post_init(app):
    await app.bot.set_my_commands(COMMAND_MENU)
    log.info("Commands menu installed.")

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init).build()

    # Core
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("pay",          cmd_pay))
    app.add_handler(CommandHandler("economy",      cmd_economy))
    app.add_handler(CommandHandler("game",         cmd_game))
    app.add_handler(CommandHandler("coupons",      cmd_coupons))
    app.add_handler(CommandHandler("own",          cmd_own))
    app.add_handler(CommandHandler("open",         cmd_open))
    app.add_handler(CommandHandler("close",        cmd_close))

    # Economy
    app.add_handler(CommandHandler("bal",          cmd_bal))
    app.add_handler(CommandHandler("daily",        cmd_daily))
    app.add_handler(CommandHandler("gems",         cmd_gems))
    app.add_handler(CommandHandler("wallet",       cmd_wallet))
    app.add_handler(CommandHandler("claim",        cmd_claim))
    app.add_handler(CommandHandler("protect",      cmd_protect))
    app.add_handler(CommandHandler("give",         cmd_give))
    app.add_handler(CommandHandler("rob",          cmd_rob))
    app.add_handler(CommandHandler("toprich",      cmd_toprich))
    app.add_handler(CommandHandler("topkill",      cmd_topkill))
    app.add_handler(CommandHandler("rank",         cmd_rank))
    app.add_handler(CommandHandler("leaders",      cmd_leaders))
    app.add_handler(CommandHandler("items",        cmd_items))
    app.add_handler(CommandHandler("item",         cmd_item))
    app.add_handler(CommandHandler("gift",         cmd_gift))

    # Games
    app.add_handler(CommandHandler("bomb",         cmd_bomb))
    app.add_handler(CommandHandler("bluff",        cmd_bluff))
    app.add_handler(CommandHandler("card",         cmd_card))
    app.add_handler(CommandHandler("hack",         cmd_hack))
    app.add_handler(CommandHandler("truth",        cmd_truth))
    app.add_handler(CommandHandler("dare",         cmd_dare))
    app.add_handler(CommandHandler("puzzle",       cmd_puzzle))

    # Fun
    for k in ("crush", "love", "hug", "kiss", "bite", "slap", "punch", "murder", "look", "brain"):
        app.add_handler(CommandHandler(k, make_fun(k)))
    app.add_handler(CommandHandler("stupid_meter", cmd_stupid))
    app.add_handler(CommandHandler("kill",         cmd_kill))
    app.add_handler(CommandHandler("revive",       cmd_revive))
    app.add_handler(CommandHandler("couples",      cmd_couples))

    # Utilities
    app.add_handler(CommandHandler("tr",           cmd_tr))
    app.add_handler(CommandHandler("voice",        cmd_voice))
    app.add_handler(CommandHandler("detail",       cmd_detail))
    app.add_handler(CommandHandler("owner",        cmd_owner))
    app.add_handler(CommandHandler("admins",       cmd_admins))
    app.add_handler(CommandHandler("pfp",          cmd_pfp))
    app.add_handler(CommandHandler("check",        cmd_check))
    app.add_handler(CommandHandler("setemoji",     cmd_setemoji))

    # Coupons
    app.add_handler(CommandHandler("redeem",       cmd_redeem))
    app.add_handler(CommandHandler("addcoupon",    cmd_addcoupon))
    app.add_handler(CommandHandler("delcoupon",    cmd_delcoupon))
    app.add_handler(CommandHandler("coupons_list", cmd_coupons_list))

    # Admin
    app.add_handler(CommandHandler("broadcast",    cmd_broadcast))
    app.add_handler(CommandHandler("ban",          cmd_ban))
    app.add_handler(CommandHandler("unban",        cmd_unban))
    app.add_handler(CommandHandler("stats",        cmd_stats))

    # Callbacks
    app.add_handler(CallbackQueryHandler(cb_bomb,  pattern=r"^bomb:"))
    app.add_handler(CallbackQueryHandler(cb_bluff, pattern=r"^bluff:"))
    app.add_handler(CallbackQueryHandler(cb_menu,  pattern=r"^menu:"))

    # Welcome + passive user tracker
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_members))
    app.add_handler(MessageHandler(filters.ALL, track_users), group=1)

    log.info("🚀 %s is running…", BOT_NAME)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
