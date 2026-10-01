from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from database import db
from services.task_manager import task_manager


def is_admin(update):
    return bool(
        update.effective_user and update.effective_user.id in settings.admin_ids
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "🛡️ *Admin Panel*\\n\\n"
        "/stats — system statistics\\n"
        "/users — registered users\\n"
        "/tasks — task statistics\\n"
        "/broadcast — broadcast information\\n"
        "/maintenance — maintenance mode status",
        parse_mode="Markdown",
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    users_count = await db.users.count_documents({})
    active = task_manager.active_count()
    running = await db.tasks.count_documents({"status": "SENDING"})
    completed = await db.tasks.count_documents({"status": "SENT"})
    cancelled = await db.tasks.count_documents({"status": "CANCELLED"})
    flood = await db.tasks.count_documents({"status": "FLOOD_WAIT"})

    await update.message.reply_text(
        f"📊 *System Statistics*\\n\\n"
        f"Users: {users_count}\\n"
        f"Active memory tasks: {active}\\n"
        f"Running: {running}\\n"
        f"Completed: {completed}\\n"
        f"Cancelled: {cancelled}\\n"
        f"Flood waits: {flood}",
        parse_mode="Markdown",
    )


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    count = await db.users.count_documents({})
    connected = await db.users.count_documents({"authenticated": True})
    await update.message.reply_text(
        f"👥 Users: {count}\\n🔐 Connected accounts: {connected}"
    )


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    rows = await db.tasks.aggregate(pipeline).to_list(length=20)
    text = "📋 *Tasks by status*\\n\\n" + "\n".join(
        f"{r['_id']}: {r['count']}" for r in rows
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "📣 Broadcast remains disabled by default. Add an explicit consent/rate policy before enabling it."
    )


async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        f"🛠️ Maintenance mode: {'ON' if settings.maintenance else 'OFF'}"
    )
