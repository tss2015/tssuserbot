from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db


async def _history_text(uid: int) -> str:
    cursor = db.tasks.find({"bot_user_id": uid}).sort("created_at", -1).limit(10)
    rows = await cursor.to_list(length=10)

    if not rows:
        return "📜 <b>Task History</b>\n\nNo task history yet."

    lines = ["📜 <b>Recent Tasks</b>"]
    for item in rows:
        status = item.get("status", "UNKNOWN")
        total = item.get("total_members", 0)
        processed = item.get("processed_members", 0)
        title = item.get("chat_title") or str(item.get("chat_id"))
        lines.append(
            f"• <code>{status}</code> — {title} — {processed}/{total}"
        )

    return "\n".join(lines)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        await _history_text(update.effective_user.id),
        parse_mode="HTML",
        reply_markup=(
            InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Back to Menu", callback_data="back:menu")]]
            )
            if update.callback_query
            else None
        ),
    )


async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        await _history_text(query.from_user.id),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Back to Menu", callback_data="back:menu")]]
        ),
    )
