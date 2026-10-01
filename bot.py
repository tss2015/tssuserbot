import asyncio
import logging
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import settings
from database import db
from handlers.account import logout, logout_callback, status
from handlers.admin import admin, broadcast, maintenance, stats, tasks, users
from handlers.authentication import auth_callback, auth_text, cancel_command, lognum, logsession
from handlers.help import help_command
from handlers.history import history
from handlers.mood import game, gm, gn, mood_command, random_mood, set_mood
from handlers.settings import settings_callback, settings_command
from handlers.start import main_menu_callback, start
from handlers.tagall import cancel, tag_callback, tagall
from services.health import start_health_server
from services.mood import MoodManager
from services.session_manager import SessionManager
from services.scheduled_messages import scheduled_loop
from services.telegram_client import manager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def post_init(app):
    await db.connect()
    import services.mood as mood_service
    mood_service.mood_manager = MoodManager(db)
    mood_service.mood_manager.bind()
    await start_health_server()
    if settings.maintenance is False and settings.enable_scheduled_messages:
        app.bot_data["scheduled_task"] = asyncio.create_task(scheduled_loop())

    # Recover authenticated sessions after a process rotation/restart.
    records = await db.users.find(
        {"authenticated": True, "encrypted_session": {"$exists": True}}
    ).to_list(length=None)

    session_manager = SessionManager(settings.session_encryption_key)
    await manager.reconnect_all(
        records, session_manager, settings.api_id, settings.api_hash
    )


async def post_shutdown(app):
    for uid in list(manager.clients):
        await manager.disconnect(uid)
    await db.close()


def build_application():
    app = Application.builder().token(settings.bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lognum", lognum))
    app.add_handler(CommandHandler("logsession", logsession))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("mood", mood_command))
    app.add_handler(CommandHandler("setmood", set_mood))
    app.add_handler(CommandHandler("randommood", random_mood))
    app.add_handler(CommandHandler("game", game))
    app.add_handler(CommandHandler("gm", gm))
    app.add_handler(CommandHandler("gn", gn))
    app.add_handler(CommandHandler("tagall", tagall))
    app.add_handler(CommandHandler("tagmood", tagall))
    app.add_handler(CommandHandler("tgallhappy", tagall))
    app.add_handler(CommandHandler("tgallsassy", tagall))
    app.add_handler(CommandHandler("tgallsulky", tagall))
    app.add_handler(CommandHandler("tgallromantic", tagall))
    app.add_handler(CommandHandler("tgallsleepy", tagall))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("maintenance", maintenance))

    app.add_handler(CallbackQueryHandler(
        tag_callback, pattern=r"^tag:(start|cancel)$"
    ))
    app.add_handler(CallbackQueryHandler(
        logout_callback, pattern=r"^logout:(ask|yes|no)$"
    ))
    app.add_handler(CallbackQueryHandler(
        settings_callback, pattern=r"^setting:(delay_up|delay_down|batch_up|batch_down)$"
    ))
    app.add_handler(CallbackQueryHandler(
        main_menu_callback,
        pattern=r"^(login:(number|session)|account:status|history|settings|help|back:menu)$",
    ))
    app.add_handler(CallbackQueryHandler(
        auth_callback, pattern=r"^auth:(digit:[0-9]|back|submit|cancel)$"
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auth_text))

    app.post_init = post_init
    app.post_shutdown = post_shutdown
    return app


if __name__ == "__main__":
    logger.info("Starting Telegram Userbot Manager")
    build_application().run_polling(allowed_updates=None)
