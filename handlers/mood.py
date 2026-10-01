from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from services.mood import MOODS
import services.mood as mood_service


async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mood = await mood_service.mood_manager.get("global")
    await update.message.reply_text(
        f"🎭 Current mood: *{mood.capitalize()}*\n\n"
        f"{mood_service.mood_manager.line(mood)}",
        parse_mode="Markdown",
    )


async def set_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.admin_ids:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /setmood <happy|sassy|sulky|romantic|sleepy>"
        )
        return

    mood = context.args[0].lower()
    if mood not in MOODS:
        await update.message.reply_text(
            "❌ Invalid mood.\nAvailable: " + ", ".join(MOODS)
        )
        return

    await mood_service.mood_manager.set(mood, "global", manual=True)
    await update.message.reply_text(
        f"🎭 Mood changed to *{mood.capitalize()}*.",
        parse_mode="Markdown",
    )


async def random_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.admin_ids:
        return

    import random
    mood = random.choice(MOODS)
    await mood_service.mood_manager.set(mood, "global", manual=False)
    await update.message.reply_text(
        f"🎲 Mood changed randomly to *{mood.capitalize()}*.",
        parse_mode="Markdown",
    )


async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mood_service.mood_manager.activity_shift("global")
    await update.message.reply_text(mood_service.mood_manager.game())


async def gm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(mood_service.mood_manager.morning())


async def gn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(mood_service.mood_manager.night())
