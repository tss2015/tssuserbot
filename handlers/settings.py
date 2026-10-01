from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import settings
from database import db


def _settings_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🐢 Delay +1s", callback_data="setting:delay_up"),
                InlineKeyboardButton("⚡ Delay -1s", callback_data="setting:delay_down"),
            ],
            [
                InlineKeyboardButton("📦 Batch +1", callback_data="setting:batch_up"),
                InlineKeyboardButton("📦 Batch -1", callback_data="setting:batch_down"),
            ],
            [
                InlineKeyboardButton("🏠 Back to Menu", callback_data="back:menu"),
            ],
        ]
    )


async def _settings_text(uid: int) -> str:
    record = await db.users.find_one({"bot_user_id": uid}) or {}
    delay = record.get("tag_delay", settings.tag_delay)
    batch = record.get("tag_batch_size", settings.tag_batch_size)
    return (
        "⚙️ <b>Your Settings</b>\n\n"
        f"Delay: <code>{delay:g}s</code>\n"
        f"Batch size: <code>{batch}</code>\n\n"
        "These values remain subject to Telegram's actual rate limits."
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        await _settings_text(update.effective_user.id),
        reply_markup=_settings_keyboard(),
        parse_mode="HTML",
    )


async def settings_callback_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        await _settings_text(query.from_user.id),
        reply_markup=_settings_keyboard(),
        parse_mode="HTML",
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
        await _settings_text(uid),
        reply_markup=_settings_keyboard(),
        parse_mode="HTML",
    )
