from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db
from services.task_manager import task_manager
from services.telegram_client import manager


async def _status_text(uid: int) -> str:
    record = await db.users.find_one({"bot_user_id": uid})
    if not record or not record.get("authenticated"):
        return "🔐 <b>Account:</b> Not connected"

    return (
        "📊 <b>Account Status</b>\n\n"
        "Connection: 🟢 Connected\n"
        f"Name: {record.get('first_name', '-')}\n"
        f"Username: @{record.get('username') or '-'}\n"
        f"Telegram ID: <code>{record.get('telegram_user_id', '-')}</code>\n"
        f"Client: {'🟢 Running' if uid in manager.clients else '🔴 Stopped'}\n"
        f"Active task: {'🟢 Yes' if task_manager.get(uid) else '⚪ No'}"
    )


def _back_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Back to Menu", callback_data="back:menu")]]
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        await _status_text(update.effective_user.id),
        parse_mode="HTML",
        reply_markup=_back_keyboard() if update.callback_query else None,
    )


async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        await _status_text(query.from_user.id),
        parse_mode="HTML",
        reply_markup=_back_keyboard(),
    )


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Logout", callback_data="logout:yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="logout:no"),
        ]
    ]
    await update.effective_message.reply_text(
        "⚠️ <b>Are you sure you want to logout?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def logout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "logout:ask":
        keyboard = [[
            InlineKeyboardButton("✅ Yes, Logout", callback_data="logout:yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="logout:no"),
        ]]
        await query.edit_message_text(
            "⚠️ <b>Are you sure you want to logout?</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "logout:no":
        await query.edit_message_text("❎ Logout cancelled.")
        return

    task_manager.cancel(uid)
    await manager.disconnect(uid)
    await db.users.delete_one({"bot_user_id": uid})
    await query.edit_message_text(
        "🚪 <b>Logged out successfully.</b>\nStored account data was removed.",
        parse_mode="HTML",
    )
