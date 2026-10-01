from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import settings
from database import db


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record = await db.users.find_one({"bot_user_id": update.effective_user.id}) or {}
    delay = record.get("tag_delay", settings.tag_delay)
    batch = record.get("tag_batch_size", settings.tag_batch_size)

    keyboard = [
        [
            InlineKeyboardButton("🐢 Delay +1s", callback_data="setting:delay_up"),
            InlineKeyboardButton("⚡ Delay -1s", callback_data="setting:delay_down"),
        ],
        [
            InlineKeyboardButton("📦 Batch +1", callback_data="setting:batch_up"),
            InlineKeyboardButton("📦 Batch -1", callback_data="setting:batch_down"),
        ],
    ]
    await update.message.reply_text(
        f"⚙️ *Your Settings*\\n\\n"
        f"Delay: `{delay:g}s`\\n"
        f"Batch size: `{batch}`\\n\\n"
        "These values are subject to Telegram's actual rate limits.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    record = await db.users.find_one({"bot_user_id": uid}) or {}
    delay = float(record.get("tag_delay", settings.tag_delay))
    batch = int(record.get("tag_batch_size", settings.tag_batch_size))

    if q.data == "setting:delay_up":
        delay = min(60, delay + 1)
    elif q.data == "setting:delay_down":
        delay = max(1, delay - 1)
    elif q.data == "setting:batch_up":
        batch = min(10, batch + 1)
    elif q.data == "setting:batch_down":
        batch = max(1, batch - 1)

    await db.users.update_one(
        {"bot_user_id": uid},
        {"$set": {"tag_delay": delay, "tag_batch_size": batch}},
        upsert=True,
    )
    await q.edit_message_text(
        f"⚙️ Settings updated\\n\\nDelay: {delay:g}s\\nBatch size: {batch}",
        parse_mode="Markdown",
    )
