import os
import json
import aiohttp
import asyncio
from datetime import datetime, date, time

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest


# ============================================================
# CONFIGURATION
# ============================================================

# Your working Like API
API_URL = os.getenv("LIKE_API_URL", "https://tg-20-likes-one.vercel.app/")
API_KEY = os.getenv("API_KEY", "CRAXX")

# IMPORTANT:
# Set BOT_TOKEN as an environment variable on your hosting platform.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8617664721:AAED06aKN2tL4Gn7awRxaCAO7mHXlm-8TR0")

# Example: ADMIN_IDS=8853678390,123456789
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "8853678390").split(",")
    if x.strip().isdigit()
]

DEFAULT_REGION = "IND"
DEFAULT_DAILY_LIMIT = 2

DATA_FILES = {
    "allowed": "allowed_groups.json",
    "stats": "daily_stats.json",
    "users": "user_limits.json",
    "config": "bot_config.json",
}


# ============================================================
# GLOBALS
# ============================================================

bot_status = "on"
bot_mode = "public"
allowed_groups = {}
daily_stats = {}
user_limits = {}
daily_limit = DEFAULT_DAILY_LIMIT


# ============================================================
# DATA
# ============================================================

def load_data():
    global allowed_groups, daily_stats, user_limits
    global bot_status, bot_mode, daily_limit

    try:
        with open(DATA_FILES["allowed"], "r", encoding="utf-8") as f:
            allowed_groups = json.load(f)
    except Exception:
        allowed_groups = {}

    try:
        with open(DATA_FILES["stats"], "r", encoding="utf-8") as f:
            daily_stats = json.load(f)
    except Exception:
        daily_stats = {}

    try:
        with open(DATA_FILES["users"], "r", encoding="utf-8") as f:
            user_limits = json.load(f)
    except Exception:
        user_limits = {}

    try:
        with open(DATA_FILES["config"], "r", encoding="utf-8") as f:
            cfg = json.load(f)
            bot_status = cfg.get("status", "on")
            bot_mode = cfg.get("mode", "public")
            daily_limit = int(cfg.get("limit", DEFAULT_DAILY_LIMIT))
    except Exception:
        bot_status = "on"
        bot_mode = "public"
        daily_limit = DEFAULT_DAILY_LIMIT


def save_all():
    with open(DATA_FILES["allowed"], "w", encoding="utf-8") as f:
        json.dump(allowed_groups, f, indent=2)

    with open(DATA_FILES["stats"], "w", encoding="utf-8") as f:
        json.dump(daily_stats, f, indent=2)

    with open(DATA_FILES["users"], "w", encoding="utf-8") as f:
        json.dump(user_limits, f, indent=2)

    with open(DATA_FILES["config"], "w", encoding="utf-8") as f:
        json.dump(
            {
                "status": bot_status,
                "mode": bot_mode,
                "limit": daily_limit,
            },
            f,
            indent=2,
        )


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def today_str():
    return str(date.today())


def can_user_like(user_id):
    if is_admin(user_id):
        return True

    today = today_str()

    if (
        user_id not in user_limits
        or user_limits[user_id].get("date") != today
    ):
        user_limits[user_id] = {"date": today, "count": 0}
        return True

    return user_limits[user_id].get("count", 0) < daily_limit


def update_user_like(user_id):
    if is_admin(user_id):
        return

    today = today_str()

    if (
        user_id not in user_limits
        or user_limits[user_id].get("date") != today
    ):
        user_limits[user_id] = {"date": today, "count": 0}

    user_limits[user_id]["count"] += 1

    if today not in daily_stats:
        daily_stats[today] = {"total": 0, "users": {}}

    daily_stats[today]["total"] += 1

    uid_str = str(user_id)
    daily_stats[today]["users"][uid_str] = (
        daily_stats[today]["users"].get(uid_str, 0) + 1
    )

    save_all()


def is_group_allowed(chat_id, chat_type):
    if chat_type == "private":
        return True

    if bot_mode == "public":
        return True

    return str(chat_id) in allowed_groups


async def reply(update: Update, text: str):
    await update.message.reply_text(text, parse_mode="Markdown")


async def block_non_admin_private(update: Update) -> bool:
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id

    if chat_type == "private" and not is_admin(user_id):
        await reply(
            update,
            "🚫 *Bot works only in groups!*\n"
            "(Admins can use it in private chat.)",
        )
        return True

    return False


# ============================================================
# LIKE API
# ============================================================

async def call_like_api(region: str, uid: str):
    """
    Calls:
    https://craxxlikeapi.vercel.app/like?uid=UID&region=IND&key=KEY
    """

    try:
        base_url = API_URL.rstrip("/") + "/like"

        params = {
            "uid": uid,
            "region": region,
        }

        if API_KEY:
            params["key"] = API_KEY

        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(base_url, params=params) as resp:

                text = await resp.text()

                if resp.status != 200:
                    return {
                        "error": f"HTTP {resp.status}",
                        "response": text[:500],
                    }

                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {
                        "error": "API returned invalid JSON",
                        "response": text[:500],
                    }

    except asyncio.TimeoutError:
        return {"error": "API request timed out"}

    except aiohttp.ClientError as e:
        return {"error": f"Network error: {e}"}

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# USER COMMANDS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update):
        return

    if bot_status == "off":
        await reply(update, "🔴 *Bot is currently OFF*")
        return

    msg = (
        "🚀 *LIKE BOT IS ACTIVE*\n\n"
        "❤️ `/like UID`\n"
        "   ↳ Send likes to your Free Fire UID\n\n"
        "🌍 Default Region: `IND`\n"
        f"🔥 Daily limit: `{daily_limit}` likes per user\n\n"
        "📌 Example:\n"
        "`/like 123456789`\n\n"
        "▹ `/help` — All commands"
    )

    await reply(update, msg)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update):
        return

    if bot_status == "off":
        await reply(update, "🔴 *Bot is OFF*")
        return

    msg = (
        "╭──────────────────╮\n"
        "   🤖 *BOT COMMAND MENU*\n"
        "╰──────────────────╯\n\n"
        "❤️ `/like UID`\n"
        "   ↳ Send profile likes\n\n"
        "ℹ️ `/info`\n"
        "   ↳ Bot status & your limit\n\n"
        "🌏 Supported region: `IND`\n\n"
        "Example:\n"
        "`/like 123456789`"
    )

    await reply(update, msg)


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update):
        return

    if bot_status == "off":
        await reply(update, "🔴 *Bot is OFF*")
        return

    user_id = update.effective_user.id

    if is_admin(user_id):
        await reply(
            update,
            "👑 *Admin Account*\n"
            "🔥 Unlimited likes — no daily limit.",
        )
        return

    today = today_str()
    used = 0

    if (
        user_id in user_limits
        and user_limits[user_id].get("date") == today
    ):
        used = user_limits[user_id].get("count", 0)

    remaining = max(0, daily_limit - used)

    msg = (
        "🤖 *BOT INFO*\n\n"
        f"⚙️ Mode: `{bot_mode.upper()}`\n"
        f"🟢 Status: `{bot_status.upper()}`\n"
        f"📅 Daily limit: `{daily_limit}`\n"
        f"✅ Used today: `{used}`\n"
        f"🟢 Remaining: `{remaining}`\n"
        f"👥 Allowed groups: `{len(allowed_groups)}`"
    )

    await reply(update, msg)


async def like_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await block_non_admin_private(update):
        return

    if bot_status == "off":
        await reply(update, "🔴 *Bot is currently OFF*")
        return

    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    if chat_type != "private" and not is_group_allowed(chat_id, chat_type):
        await reply(update, "🚫 *This bot works only in allowed groups!*")
        return

    # New simple command:
    # /like UID
    #
    # Also accepts old format:
    # /like IND UID
    if len(context.args) == 1:
        region = DEFAULT_REGION
        uid = context.args[0]

    elif len(context.args) == 2:
        region = context.args[0].upper()
        uid = context.args[1]

    else:
        await reply(
            update,
            "❌ *Incorrect command!*\n\n"
            "Use:\n"
            "`/like UID`\n\n"
            "Example:\n"
            "`/like 123456789`\n\n"
            "Default region: `IND`",
        )
        return

    if not uid.isdigit():
        await reply(update, "❌ *UID must contain only numbers!*")
        return

    if len(uid) < 5:
        await reply(update, "❌ *Please enter a valid UID.*")
        return

    if region != DEFAULT_REGION:
        await reply(
            update,
            "❌ *Unsupported region!*\n"
            "Currently supported region: `IND`",
        )
        return

    user_id = update.effective_user.id

    if not can_user_like(user_id):
        used = user_limits.get(user_id, {}).get("count", 0)

        await reply(
            update,
            "⚠️ *Daily limit reached!*\n"
            f"You have used `{used}/{daily_limit}` likes today.\n"
            "💡 Try again tomorrow.",
        )
        return

    proc_msg = await update.message.reply_text(
        f"🔄 *Processing likes...*\n\n"
        f"🆔 UID: `{uid}`\n"
        f"🌏 Region: `{region}`",
        parse_mode="Markdown",
    )

    data = await call_like_api(region, uid)

    if not data or "error" in data:
        error_msg = (
            data.get("error", "No response")
            if data
            else "No response from API"
        )

        await proc_msg.edit_text(
            "⚠️ *LIMIT REACHED* ⚠️\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ᴜɪᴅ : {uid}\n"
            f"👤 ɴᴀᴍᴇ: {data.get('PlayerNickname', 'Unknown') if data else 'Unknown'}\n\n"
            "⚡ᴛʜɪꜱ ɪᴅ ʜᴀꜱ ʀᴇᴀᴄʜᴇᴅ ᴍᴀxɪᴍᴜᴍ ʟɪᴋᴇꜱ ꜰᴏʀ ᴛᴏᴅᴀʏ,  ᴛʀʏ ᴀɢᴀɪɴ ᴛᴏᴍᴏʀʀᴏᴡ.\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown",
        )
        return

    status = data.get("status")

    if status is None:
        await proc_msg.edit_text(
            "❌ *Invalid API response*\n"
            "The server returned an unexpected format.",
            parse_mode="Markdown",
        )
        return

    player = data.get("PlayerNickname", "Unknown")
    uid_resp = data.get("UID", uid)
    region_resp = data.get("Region", region)
    level = data.get("Level", "N/A")

    before = data.get("LikesbeforeCommand", 0)
    after = data.get("LikesafterCommand", 0)
    given = data.get("LikesGivenByAPI", 0)

    if status == 1:
        update_user_like(user_id)

        user_used = (
            "Unlimited"
            if is_admin(user_id)
            else user_limits.get(user_id, {}).get("count", 0)
        )

        result = (
            "✅ *Autolike Success!*\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👤 ɴᴀᴍᴇ: {player}\n"
            f"🆔 ᴜɪᴅ: {uid_resp}\n"
            f"🌏 ʀᴇɢɪᴏɴ: {region_resp}\n\n"
            "❤️ ʟɪᴋᴇs sᴛᴀᴛᴜs -\n"
            f" ├─ ʙᴇғᴏʀᴇ: {before:,}\n"
            f" ├─ ɢɪᴠᴇɴ: +{given:,}\n"
            f" └─ ᴀғᴛᴇʀ: {after:,}\n\n"
            f"⚙️ ᴅᴀɪʟʏ ʟɪᴍɪᴛ : {daily_limit}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

    elif status == 2:
        result = (
            "🚫 *Daily Limit Reached!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ɴᴀᴍᴇ: {player}\n"
            f"🆔 ᴜɪᴅ: {uid_resp}\n"
            f"🌏 ʀᴇɢɪᴏɴ: {region_resp}\n\n"
            f"📉 ʙᴇғᴏʀᴇ: {before:,}\n"
            f"📈 ᴀғᴛᴇʀ: {before:,}\n"
            "❤️ ɢɪᴠᴇɴ: +0\n\n"
            "⌛ᴅᴀɪʟʏ ꜰʀᴇᴇ ʟɪᴋᴇꜱ ʟɪᴍɪᴛ ꜰᴏʀ ᴛʜɪꜱ ᴜɪᴅ ɪꜱ ꜰᴜʟʟ, ᴛʀʏ ᴀɢᴀɪɴ ᴀꜰᴛᴇʀ 𝟨 ʜᴏᴜʀꜱ.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )

    else:
        result = (
            "❓ *Unknown API response*\n\n"
            f"Status code: `{status}`\n"
            "Please contact the bot admin."
        )

    await proc_msg.edit_text(result, parse_mode="Markdown")


# ============================================================
# ADMIN COMMANDS
# ============================================================

async def allow_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only command*")
        return

    chat = update.effective_chat

    if chat.type == "private":
        await reply(update, "❌ Use this command in a group")
        return

    gid = str(chat.id)

    allowed_groups[gid] = {
        "name": chat.title,
        "by": update.effective_user.id,
        "date": today_str(),
    }

    save_all()

    await reply(
        update,
        f"✅ *Group allowed*\n"
        f"{chat.title}\n"
        "Bot will now work here when private mode is enabled.",
    )


async def off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    global bot_status
    bot_status = "off"
    save_all()

    await reply(update, "🔴 *Bot is now OFF*")


async def on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    global bot_status
    bot_status = "on"
    save_all()

    await reply(update, "🟢 *Bot is now ON*")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    today = today_str()

    if today not in daily_stats:
        await reply(update, "📊 *No stats for today*")
        return

    total = daily_stats[today]["total"]
    users_count = len(daily_stats[today]["users"])

    msg = (
        "📊 *TODAY'S STATS*\n\n"
        f"📅 Date: `{today}`\n"
        f"❤️ Total likes sent: `{total}`\n"
        f"👥 Users: `{users_count}`\n"
        f"⚙️ Limit per user: `{daily_limit}`\n"
        f"🎯 Mode: `{bot_mode.upper()}`"
    )

    await reply(update, msg)


async def set_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    global bot_mode
    bot_mode = "private"
    save_all()

    await reply(
        update,
        "🔒 *Bot is now PRIVATE*\n"
        "Works only in allowed groups.",
    )


async def set_public(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    global bot_mode
    bot_mode = "public"
    save_all()

    await reply(
        update,
        "🌍 *Bot is now PUBLIC*\n"
        "Works in all groups.",
    )


async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await reply(update, "❌ *Admin only*")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await reply(
            update,
            "❌ Usage: `/setlimit <number>`\n"
            "Example: `/setlimit 5`",
        )
        return

    global daily_limit
    daily_limit = int(context.args[0])
    save_all()

    await reply(
        update,
        f"✅ *Daily limit set to `{daily_limit}` likes per user*",
    )


# ============================================================
# DAILY RESET
# ============================================================

async def reset_midnight(context: ContextTypes.DEFAULT_TYPE):
    global user_limits
    user_limits = {}
    save_all()
    print(f"[{datetime.now()}] ✅ Daily limits reset")


# ============================================================
# MAIN
# ============================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    load_data()

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )

    job_queue = app.job_queue

    if job_queue:
        job_queue.run_daily(
            reset_midnight,
            time=time(hour=0, minute=0, second=0),
            days=tuple(range(7)),
        )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("like", like_cmd))

    app.add_handler(CommandHandler("allow", allow_group))
    app.add_handler(CommandHandler("off", off_cmd))
    app.add_handler(CommandHandler("on", on_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("setprivate", set_private))
    app.add_handler(CommandHandler("setpublic", set_public))
    app.add_handler(CommandHandler("setlimit", set_limit))

    print("🤖 Bot is running...")
    print("❤️ /like UID -> IND")
    print(f"📅 Daily limit -> {daily_limit}")

    app.run_polling()


if __name__ == "__main__":
    main()