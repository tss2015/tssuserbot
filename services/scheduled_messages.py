import asyncio
from datetime import datetime, timezone

from database import db
import services.mood as mood_service
from services.telegram_client import manager


async def scheduled_loop():
    """
    Optional lightweight scheduler.
    It only sends to chats explicitly stored in `scheduled_chats`.
    No group is discovered or messaged automatically.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            hhmm = now.strftime("%H:%M")

            records = await db.db.scheduled_chats.find(
                {"enabled": True, "times": hhmm}
            ).to_list(length=100)

            for record in records:
                uid = record.get("bot_user_id")
                chat_id = record.get("chat_id")
                client = manager.clients.get(uid)
                if not client:
                    continue

                if record.get("type") == "morning":
                    text = mood_service.mood_manager.morning()
                elif record.get("type") == "night":
                    text = mood_service.mood_manager.night()
                else:
                    text = mood_service.mood_manager.game()

                try:
                    await client.send_message(chat_id, text)
                except Exception:
                    # Scheduler should never kill the main process.
                    continue

        finally:
            await asyncio.sleep(60)
