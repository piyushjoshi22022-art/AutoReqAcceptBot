import os
from datetime import date
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient

# ================== ENV VARIABLES ==================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONGO_URL = os.getenv("MONGO_URL")

# ================== BOT CLIENT ==================
app = Client(
    "auto_request_accept_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================== MONGODB ==================
mongo = MongoClient(MONGO_URL)
db = mongo["autoreqacceptbot"]

users_col = db.users          # /start users
stats_col = db.stats          # stats storage

# ================== INIT STATS ==================
today = date.today()

if not stats_col.find_one({"_id": "stats"}):
    stats_col.insert_one({
        "_id": "stats",
        "today": 0,
        "month": 0,
        "total": 0,
        "date": today.isoformat(),
        "month_no": today.month
    })

# ================== AUTO ACCEPT JOIN REQUEST ==================
@app.on_chat_join_request()
async def approve_request(client, req):
    await client.approve_chat_join_request(req.chat.id, req.from_user.id)

    stats = stats_col.find_one({"_id": "stats"})
    today = date.today()

    # reset daily
    if stats["date"] != today.isoformat():
        stats_col.update_one(
            {"_id": "stats"},
            {"$set": {"today": 0, "date": today.isoformat()}}
        )

    # reset monthly
    if stats["month_no"] != today.month:
        stats_col.update_one(
            {"_id": "stats"},
            {"$set": {"month": 0, "month_no": today.month}}
        )

    stats_col.update_one(
        {"_id": "stats"},
        {"$inc": {"today": 1, "month": 1, "total": 1}}
    )

    try:
        await client.send_message(
            req.from_user.id,
            f"Hello {req.from_user.first_name},\n\n"
            f"Your request to join **{req.chat.title}** has been approved.\n\n"
            f"Send /start to use the bot."
        )
    except:
        pass

# ================== /START ==================
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id

    # save user permanently
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Bot Updates", url="https://t.me/AutoAccepter")],
        [
            InlineKeyboardButton(
                "➕ Add To Group",
                url="https://t.me/AutoReqAccept1Bot?startgroup=true&admin=invite_users+manage_chat"
            ),
            InlineKeyboardButton(
                "➕ Add To Channel",
                url="https://t.me/AutoReqAccept1Bot?startchannel=true&admin=invite_users+manage_chat"
            )
        ],
        [InlineKeyboardButton("📊 Statistics", callback_data="stats")]
    ])

    await message.reply(
        "Add **@AutoReqAccept1Bot** to your Channel/Group to auto accept join requests 😊",
        reply_markup=buttons
    )

# ================== STATS BUTTON ==================
@app.on_callback_query(filters.regex("^stats$"))
async def stats_cb(client, cb):
    stats = stats_col.find_one({"_id": "stats"})

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data="back")]
    ])

    await cb.message.edit_text(
        f"📊 **Statistics**\n\n"
        f"Today Accepted: `{stats['today']}`\n"
        f"Monthly Accepted: `{stats['month']}`\n"
        f"Total Accepted: `{stats['total']}`",
        reply_markup=buttons
    )

# ================== BACK BUTTON ==================
@app.on_callback_query(filters.regex("^back$"))
async def back_cb(client, cb):
    await start_cmd(client, cb.message)

# ================== /USERS (OWNER ONLY) ==================
@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def users_cmd(client, message):
    total = users_col.count_documents({})
    await message.reply(f"👥 Total Users (Started Bot): `{total}`")

# ================== /BROADCAST (OWNER ONLY) ==================
@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a message to broadcast")

    sent = 0
    removed = 0

    for user in users_col.find():
        user_id = user["user_id"]
        try:
            await message.reply_to_message.copy(user_id)
            sent += 1
        except:
            users_col.delete_one({"user_id": user_id})
            removed += 1

    await message.reply(
        f"✅ Broadcast Completed\n\n"
        f"Sent: `{sent}`\n"
        f"Removed (Blocked): `{removed}`"
    )

# ================== RUN ==================
app.run()
