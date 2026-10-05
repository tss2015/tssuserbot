import asyncio
import html
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telethon.errors import FloodWaitError, RPCError

import services.mood as mood_service
from config import settings
from database import db
from services.ai_mood import groq_mood
from services.member_collector import eligible_members
from services.mention_manager import batches, mention
from services.rate_limiter import RateLimiter
from services.task_manager import UserTask, task_manager
from services.telegram_client import manager
from utils.helpers import human_seconds, utcnow

logger = logging.getLogger(__name__)
limiter = RateLimiter()

MOOD_ALIASES = {mood: mood for mood in mood_service.MOODS}

TAG_COMMAND_ALIASES = {
    "/tagall",
    "/tagmood",
    "/tgallhappy",
    "/tgallsassy",
    "/tgallsulky",
    "/tgallromantic",
    "/tgallsleepy",
}


def _parse_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[str | None, str | None]:
    """Parse tag command mood and optional custom instruction.

    Supported forms:
      /tagall
      /tagall romantic
      /tagall romantic hello everyone
      /tagmood romantic
      /tagmood romantic hello
      /tgallhappy
      /tgallsassy
      /tgallsulky
      /tgallromantic
      /tgallsleepy
    """
    args = list(context.args or [])

    message = update.effective_message
    text = message.text if message else ""

    command = ""

    if text:
        command = text.strip().split()[0].split("@", 1)[0].lower()

    alias_mood = None

    if command.startswith("/tgall"):
        alias_mood = command.removeprefix("/tgall")

    elif command == "/tagmood":
        alias_mood = ""

    mood = MOOD_ALIASES.get(alias_mood)

    if args and args[0].lower() in MOOD_ALIASES:
        mood = args.pop(0).lower()

    instruction = " ".join(args).strip() or None

    return mood, instruction


async def _is_group_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if not update.effective_chat:
        return False

    if update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return False

    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id,
        )

        return member.status in (
            "administrator",
            "creator",
        )

    except TelegramError:
        return False


async def _login_required(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🔐 Your Telegram account is not connected to the userbot.\n\n"
        "Please open my private chat and use:\n"
        "/lognum — login with your phone number\n"
        "/logsession — login with an existing StringSession"
    )

    try:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
        )

    except TelegramError:
        if update.effective_message:
            await update.effective_message.reply_text(
                "🔐 Your Telegram account is not connected. "
                "Open the bot in private chat and use "
                "/lognum or /logsession."
            )


async def _generate_unique_mood_message(
    mood: str,
    member,
    group_title: str | None,
    member_count: int,
    used_messages: set[str],
) -> str:
    """Generate a fresh mood message for one participant."""

    member_name = (
        getattr(member, "first_name", None)
        or getattr(member, "username", None)
        or "friend"
    )

    recent_messages = list(used_messages)[-5:]

    if recent_messages:
        previous_messages = "\n".join(
            f"- {message}"
            for message in recent_messages
        )
    else:
        previous_messages = "- None"

    instruction = (
f"Create one fresh and unique {mood} message "
    f"for the Telegram user named {member_name}.\n\n"
    "Keep the message natural, concise and suitable "
    "for a Telegram group.\n"
    "Do not mention AI.\n"
    "Do not mention prompts or instructions.\n"
    "Do not copy any previously generated message.\n"
    "Use different wording from the previous messages.\n\n"
    f"Group: {group_title or 'Telegram group'}\n"
    f"Eligible members: {member_count}\n\n"
    "Previously generated messages:\n"
    f"{previous_messages}"
    )

    for attempt in range(3):
        try:
            generated = await groq_mood.generate(
                mood=mood,
                instruction=instruction,
                group_title=group_title,
                member_count=member_count,
            )

            generated = (generated or "").strip()

            if not generated:
                continue

            existing = {
                value.casefold()
                for value in used_messages
            }

            if generated.casefold() not in existing:
                used_messages.add(generated)
                return generated

            instruction += (
                "\n\nThe previous response duplicated an existing "
                "message. Generate substantially different wording."
            )

        except Exception as exc:
            logger.warning(
                "AI mood generation failed for member=%s "
                "attempt=%s: %s",
                getattr(member, "id", "?"),
                attempt + 1,
                exc,
            )

    # Local fallback if AI generation fails.
    fallback = (
        mood_service.mood_manager.line(mood) or ""
    ).strip()

    existing = {
        value.casefold()
        for value in used_messages
    }

    if fallback and fallback.casefold() not in existing:
        used_messages.add(fallback)
        return fallback

    if fallback:
        unique_fallback = (
            f"{fallback} — {member_name}"
        )
    else:
        unique_fallback = (
            f"Hey {member_name}, just checking in! 😊"
        )

    used_messages.add(unique_fallback)

    return unique_fallback


async def tagall(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user:
        return

    if not update.effective_chat:
        return

    uid = update.effective_user.id
    chat = update.effective_chat

    if chat.type not in (
        "group",
        "supergroup",
    ):
        await update.effective_message.reply_text(
            "❌ Tagging only works in a group or supergroup."
        )
        return

    if not await _is_group_admin(
        update,
        context,
    ):
        await update.effective_message.reply_text(
            "❌ Only group admins can use user tagging."
        )
        return

    client = manager.clients.get(uid)

    if not client:
        await _login_required(
            update,
            context,
        )
        return

    # Reconnect the user's own Telegram session.
    try:
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await _login_required(
                update,
                context,
            )
            return

    except (
        RPCError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning(
            "User session unavailable for %s: %s",
            uid,
            exc,
        )

        await update.effective_message.reply_text(
            "❌ Your connected Telegram session is unavailable. "
            "Please login again in private chat."
        )
        return

    if task_manager.get(uid):
        await update.effective_message.reply_text(
            "⚠️ You already have an active task. "
            "Use /cancel first."
        )
        return

    mood, instruction = _parse_request(
        update,
        context,
    )

    if mood is None:
        mood = await mood_service.mood_manager.activity_shift(
            f"chat:{chat.id}"
        )

    record = await db.users.find_one(
        {"bot_user_id": uid}
    ) or {}

    max_members = settings.max_members_per_task

    try:
        members = await eligible_members(
            client,
            chat.id,
            max_members,
        )

    except (
        RPCError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning(
            "Member collection failed for user=%s chat=%s: %s",
            uid,
            chat.id,
            exc,
        )

        await update.effective_message.reply_text(
            "❌ I could not read the group members with your "
            "connected Telegram account.\n\n"
            "Make sure that account is a member of this group "
            "and try again."
        )
        return

    if not members:
        await update.effective_message.reply_text(
            "ℹ️ No eligible members were found."
        )
        return

    delay = max(
        1.0,
        float(
            record.get(
                "tag_delay",
                settings.tag_delay,
            )
        ),
    )

    batch_size = max(
        1,
        min(
            10,
            int(
                record.get(
                    "tag_batch_size",
                    settings.tag_batch_size,
                )
            ),
        ),
    )

    # ---------------------------------------------------------
    # CUSTOM MESSAGE MODE
    #
    # /tagall plz join vc
    #
    # Exact custom message is sent to everyone.
    # No AI rewriting.
    # ---------------------------------------------------------
    custom_message_mode = bool(instruction)

    if custom_message_mode:
        effective_batch_size = batch_size
        preview_message = instruction

    # ---------------------------------------------------------
    # MOOD MODE
    #
    # One participant per message is required because each
    # participant must receive a different AI-generated message.
    # ---------------------------------------------------------
    else:
        effective_batch_size = 1

        preview_message = (
            f"A unique {mood} AI message will be generated "
            "for each participant."
        )

    estimated = (
        len(members)
        * delay
        / max(1, effective_batch_size)
    )

    task_id = str(uuid.uuid4())

    await db.tasks.insert_one(
        {
            "task_id": task_id,
            "bot_user_id": uid,
            "chat_id": chat.id,
            "chat_title": chat.title,
            "task_type": "tagall",
            "mood": mood,
            "instruction": instruction,
            "message_text": (
                instruction
                if custom_message_mode
                else None
            ),
            "ai_message": (
                instruction
                if custom_message_mode
                else None
            ),
            "unique_per_member": not custom_message_mode,
            "status": "QUEUED",
            "total_members": len(members),
            "processed_members": 0,
            "successful": 0,
            "failed": 0,
            "created_at": utcnow(),
        }
    )

    context.user_data["pending_tag"] = (
        task_id,
        chat.id,
        chat.title,
        members,
        delay,
        effective_batch_size,
        mood,
        instruction,
        custom_message_mode,
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "▶️ Start Tagging",
                callback_data="tag:start",
            ),
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="tag:cancel",
            ),
        ]
    ]

    if custom_message_mode:
        message_preview = html.escape(
            instruction
        )

        mode_text = (
            "📝 <b>Your custom message will be sent "
            "exactly as entered.</b>"
        )

    else:
        message_preview = html.escape(
            preview_message
        )

        mode_text = (
            "✨ <b>Each participant will receive a "
            "different AI-generated message.</b>"
        )

    preview = (
        "🤖 <b>AI Tagging Preview</b>\n\n"
        f"🎭 <b>Mood:</b> {html.escape(mood)}\n"
        f"💬 <b>Message:</b> {message_preview}\n\n"
        f"👥 <b>Group:</b> "
        f"{html.escape(chat.title or '-')}\n"
        f"📊 <b>Eligible members:</b> {len(members)}\n"
        f"📦 <b>Batch size:</b> {effective_batch_size}\n"
        f"⏱️ <b>Delay:</b> {delay:g}s\n"
        f"🕐 <b>Estimated minimum duration:</b> "
        f"{html.escape(human_seconds(estimated))}\n\n"
        "📱 Messages will be sent from "
        "<b>your connected Telegram account</b>.\n"
        f"{mode_text}\n"
        "🛡️ Telegram FloodWait/rate limits are respected."
    )

    await update.effective_message.reply_text(
        preview,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="HTML",
    )


async def tag_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    if query.data == "tag:cancel":
        context.user_data.pop(
            "pending_tag",
            None,
        )

        await query.edit_message_text(
            "❌ Tag operation cancelled."
        )
        return

    if task_manager.get(uid):
        await query.edit_message_text(
            "⚠️ You already have a running task."
        )
        return

    pending = context.user_data.pop(
        "pending_tag",
        None,
    )

    if not pending:
        await query.edit_message_text(
            "⌛ This operation has expired. "
            "Run /tagall again."
        )
        return

    (
        task_id,
        chat_id,
        chat_title,
        members,
        delay,
        batch_size,
        mood,
        instruction,
        custom_message_mode,
    ) = pending

    client = manager.clients.get(uid)

    if not client:
        await query.edit_message_text(
            "🔐 Your userbot session is no longer connected. "
            "Please login again."
        )
        return

    try:
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            await query.edit_message_text(
                "🔐 Your userbot session is no longer authorized. "
                "Please login again."
            )
            return

    except (
        RPCError,
        OSError,
        ValueError,
    ):
        await query.edit_message_text(
            "🔐 Your Telegram session is unavailable. "
            "Please login again."
        )
        return

    item = UserTask(
        task_id,
        uid,
        chat_id,
    )

    task_manager.add(item)

    item.task = asyncio.create_task(
        run_tagging(
            query,
            item,
            members,
            delay,
            batch_size,
            mood,
            chat_title,
            instruction,
            custom_message_mode,
        )
    )


async def run_tagging(
    query,
    item: UserTask,
    members,
    delay,
    batch_size,
    mood,
    chat_title,
    instruction,
    custom_message_mode,
):
    uid = item.bot_user_id
    client = manager.clients.get(uid)

    sent = 0
    failed = 0
    processed = 0
    flood_wait_count = 0
    total = len(members)

    # Used to avoid intentionally reusing AI-generated messages.
    used_messages: set[str] = set()

    await db.tasks.update_one(
        {"task_id": item.task_id},
        {
            "$set": {
                "status": "SENDING",
                "started_at": utcnow(),
            }
        },
    )

    try:
        if not client:
            raise RuntimeError(
                "Userbot client disconnected before sending"
            )

        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            raise RuntimeError(
                "Userbot session is no longer authorized"
            )

        for batch in batches(
            members,
            batch_size,
        ):
            if item.cancel_event.is_set():
                await db.tasks.update_one(
                    {"task_id": item.task_id},
                    {
                        "$set": {
                            "status": "CANCELLED",
                            "processed_members": processed,
                            "successful": sent,
                            "failed": failed,
                            "completed_at": utcnow(),
                        }
                    },
                )

                await query.edit_message_text(
                    "🛑 <b>Tagging cancelled.</b>\n\n"
                    f"Processed: {processed}/{total}\n"
                    f"✅ Sent: {sent}\n"
                    f"❌ Failed: {failed}",
                    parse_mode="HTML",
                )
                return

            # -------------------------------------------------
            # Generate the message ONCE for this batch.
            #
            # Mood mode has batch_size=1, therefore each
            # participant gets a separate AI-generated message.
            #
            # Custom mode keeps the exact original message.
            # -------------------------------------------------
            if custom_message_mode:
                message_text = instruction

            else:
                member = batch[0]

                message_text = (
                    await _generate_unique_mood_message(
                        mood=mood,
                        member=member,
                        group_title=chat_title,
                        member_count=total,
                        used_messages=used_messages,
                    )
                )

                await db.tasks.update_one(
                    {"task_id": item.task_id},
                    {
                        "$set": {
                            "last_ai_message": message_text,
                        }
                    },
                )

            while True:
                try:
                    await limiter.wait(
                        f"{uid}:{item.chat_id}",
                        delay,
                    )

                    mentions = " ".join(
                        mention(user)
                        for user in batch
                    )

                    payload = (
                        f"{html.escape(message_text)}\n\n"
                        f"{mentions}"
                    )

                    await client.send_message(
                        item.chat_id,
                        payload,
                        link_preview=False,
                        parse_mode="html",
                    )

                    sent += len(batch)
                    break

                except FloodWaitError as exc:
                    flood_wait_count += 1

                    await db.tasks.update_one(
                        {"task_id": item.task_id},
                        {
                            "$set": {
                                "status": "FLOOD_WAIT",
                                "flood_wait_seconds": exc.seconds,
                                "processed_members": processed,
                                "successful": sent,
                                "failed": failed,
                            }
                        },
                    )

                    await query.edit_message_text(
                        "⏸️ <b>Telegram FloodWait</b>\n\n"
                        "Telegram requested a pause of "
                        f"<b>{exc.seconds}s</b>.\n"
                        f"Processed: {processed}/{total}\n\n"
                        "The task will wait for Telegram's requested "
                        "period before attempting to continue.",
                        parse_mode="HTML",
                    )

                    await asyncio.sleep(
                        exc.seconds
                    )

                    if flood_wait_count >= 2:
                        await query.edit_message_text(
                            "🛑 <b>Tagging stopped after "
                            "repeated FloodWait.</b>\n\n"
                            f"Processed: {processed}/{total}\n"
                            f"✅ Sent: {sent}\n"
                            f"❌ Failed: {failed}",
                            parse_mode="HTML",
                        )
                        return

                    # Retry the SAME generated message.
                    continue

                except (
                    RPCError,
                    OSError,
                    ValueError,
                ) as exc:
                    failed += len(batch)

                    logger.warning(
                        "Tag send failed: "
                        "user=%s chat=%s batch=%s error=%s",
                        uid,
                        item.chat_id,
                        len(batch),
                        exc,
                    )
                    break

            processed += len(batch)

            await db.tasks.update_one(
                {"task_id": item.task_id},
                {
                    "$set": {
                        "processed_members": processed,
                        "successful": sent,
                        "failed": failed,
                    }
                },
            )

            if (
                processed == total
                or processed % max(
                    batch_size * 5,
                    10,
                ) == 0
            ):
                if custom_message_mode:
                    mode_status = (
                        "📝 Exact custom message"
                    )
                else:
                    mode_status = (
                        "✨ Unique AI message per participant"
                    )

                progress = (
                    "📢 <b>AI tagging in progress</b>\n\n"
                    f"🎭 Mood: "
                    f"<code>{html.escape(mood)}</code>\n"
                    f"📊 Progress: {processed}/{total}\n"
                    f"✅ Sent: {sent}\n"
                    f"❌ Failed: {failed}\n"
                    f"⏱️ Delay: {delay:g}s\n"
                    f"{mode_status}"
                )

                await query.edit_message_text(
                    progress,
                    parse_mode="HTML",
                )

        await db.tasks.update_one(
            {"task_id": item.task_id},
            {
                "$set": {
                    "status": "SENT",
                    "processed_members": processed,
                    "successful": sent,
                    "failed": failed,
                    "completed_at": utcnow(),
                }
            },
        )

        if custom_message_mode:
            completion_mode = (
                "📝 Your custom message was sent "
                "exactly as entered."
            )
        else:
            completion_mode = (
                "✨ Every participant received a "
                "unique AI-generated message."
            )

        completion = (
            "✅ <b>AI tagging completed</b>\n\n"
            f"🎭 Mood: {html.escape(mood)}\n"
            f"📊 Processed: {processed}\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}\n\n"
            f"{completion_mode}"
        )

        await query.edit_message_text(
            completion,
            parse_mode="HTML",
        )

    except (
        RuntimeError,
        RPCError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning(
            "Tagging task %s stopped: %s",
            item.task_id,
            exc,
        )

        await db.tasks.update_one(
            {"task_id": item.task_id},
            {
                "$set": {
                    "status": "FAILED",
                    "processed_members": processed,
                    "successful": sent,
                    "failed": failed,
                    "error": str(exc)[:500],
                    "completed_at": utcnow(),
                }
            },
        )

        await query.edit_message_text(
            "❌ <b>Tagging stopped</b>\n\n"
            f"Processed: {processed}/{total}\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}\n\n"
            "Please check the connected Telegram session "
            "and try again.",
            parse_mode="HTML",
        )

    finally:
        task_manager.remove(uid)


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    uid = update.effective_user.id

    if task_manager.cancel(uid):
        await update.effective_message.reply_text(
            "🛑 Cancellation requested."
        )
    else:
        await update.effective_message.reply_text(
            "ℹ️ No active tagging task."
        )
