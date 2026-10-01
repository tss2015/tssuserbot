from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db
from services.task_manager import task_manager
from services.telegram_client import manager


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record = await db.users.find_one({"bot_user_id": update.effective_user.id})
    if not record or not record.get("authenticated"):
        await update.message.reply_text("🔐 Account: Not connected")
        return

    uid = update.effective_user.id
    await update.message.reply_text(
        "📊 *Account Status*\\n"
        f"Connection: Connected\\n"
        f"Name: {record.get('first_name', '-')}\\n"
        f"Username: @{record.get('username') or '-'}\\n"
        f"Telegram ID: {record.get('telegram_user_id', '-')}\\n"
        f"Client: {'Running' if uid in manager.clients else 'Stopped'}\\n"
        f"Active task: {'Yes' if task_manager.get(uid) else 'No'}",
        parse_mode="Markdown",
    )


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("✅ Yes, Logout", callback_data="logout:yes"),
        InlineKeyboardButton("❌ Cancel", callback_data="logout:no"),
    ]]
    await update.message.reply_text(
        "⚠️ Are you sure you want to logout?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def logout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "logout:no":
        await query.edit_message_text("Logout cancelled.")
        return

    task_manager.cancel(uid)
    await manager.disconnect(uid)
    await db.users.delete_one({"bot_user_id": uid})
    await query.edit_message_text("🚪 Logged out successfully. Stored account data was removed.")
