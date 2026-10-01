from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

TEXT = """📚 *Telegram Userbot Manager*

Account:
/start — control panel
/help — this help
/lognum — phone login flow *(private chat only)*
/logsession — existing StringSession *(private chat only)*
/status — account status
/settings — personal tagging settings
/history — recent task history
/mood — current bot mood
/setmood — change mood
/randommood — random mood
/game — mood game
/gm — good morning message
/gn — good night message
/logout — disconnect account

Tasks:
/tagall — tagging preview using current/automatic mood
/tagmood <mood> [message] — tag using a selected mood
/tgallhappy — happy tagging
/tgallsassy — sassy tagging
/tgallsulky — sulky tagging
/tgallromantic — romantic tagging
/tgallsleepy — sleepy tagging
/cancel — cancel active tagging

Mood values:
happy | sassy | sulky | romantic | sleepy

Admin:
/admin /stats /users /tasks /broadcast /maintenance

Security:
• Sessions are encrypted at rest.
• OTPs and 2FA passwords are never stored.
• Per-user sessions and tasks are isolated.
• FloodWait is respected; no anti-spam bypass is attempted.
"""

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        TEXT,
        parse_mode="Markdown",
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        TEXT,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Back to Menu", callback_data="back:menu")]]
        ),
    )
