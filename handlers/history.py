from telegram import Update
from telegram.ext import ContextTypes

from database import db


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db.tasks.find(
        {"bot_user_id": update.effective_user.id}
    ).sort("created_at", -1).limit(10)

    rows = await cursor.to_list(length=10)
    if not rows:
        await update.message.reply_text("📜 No task history yet.")
        return

    lines = ["📜 *Recent Tasks*"]
    for item in rows:
        status = item.get("status", "UNKNOWN")
        total = item.get("total_members", 0)
        processed = item.get("processed_members", 0)
        title = item.get("chat_title") or str(item.get("chat_id"))
        lines.append(f"• `{status}` — {title} — {processed}/{total}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
