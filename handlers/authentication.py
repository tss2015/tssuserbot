import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.errors import (
    AuthKeyUnregisteredError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from config import settings
from database import db
from services.session_manager import SessionManager
from services.telegram_client import manager

session_manager = SessionManager(settings.session_encryption_key)
AUTH_CLIENTS: dict[int, TelegramClient] = {}

OTP_LENGTH = 5


def _otp_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="auth:digit:1"),
            InlineKeyboardButton("2", callback_data="auth:digit:2"),
            InlineKeyboardButton("3", callback_data="auth:digit:3"),
        ],
        [
            InlineKeyboardButton("4", callback_data="auth:digit:4"),
            InlineKeyboardButton("5", callback_data="auth:digit:5"),
            InlineKeyboardButton("6", callback_data="auth:digit:6"),
        ],
        [
            InlineKeyboardButton("7", callback_data="auth:digit:7"),
            InlineKeyboardButton("8", callback_data="auth:digit:8"),
            InlineKeyboardButton("9", callback_data="auth:digit:9"),
        ],
        [
            InlineKeyboardButton("↩️ Back", callback_data="auth:back"),
            InlineKeyboardButton("0", callback_data="auth:digit:0"),
            InlineKeyboardButton(
                "✅ Submit",
                callback_data="auth:submit",
            ),
        ],
        [
            InlineKeyboardButton("❌ Cancel Login", callback_data="auth:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _masked_code(code: str) -> str:
    return "".join("●" for _ in code) + "○" * max(0, OTP_LENGTH - len(code))


def _code_message() -> str:
    return (
        "📨 <b>Telegram just sent a login code</b>.\n\n"
        "Enter the 5-digit code using the keypad below.\n"
        "Do not send the code as a normal message elsewhere.\n\n"
        "🔐 <b>Code:</b> <code>{code}</code>\n\n"
        "Send /cancel at any time to stop and securely erase this login state."
    )


async def _clear_auth(uid: int, context: ContextTypes.DEFAULT_TYPE):
    client = AUTH_CLIENTS.pop(uid, None)
    if client:
        await client.disconnect()
    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
        "auth_code",
    ):
        context.user_data.pop(key, None)


async def _save_authenticated_client(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: TelegramClient,
):
    uid = update.effective_user.id
    me = await client.get_me()
    session = client.session.save()
    encrypted = session_manager.encrypt(session)

    await db.users.update_one(
        {"bot_user_id": uid},
        {
            "$set": {
                "bot_user_id": uid,
                "telegram_user_id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "authenticated": True,
                "encrypted_session": encrypted,
            }
        },
        upsert=True,
    )

    await manager.attach_client(uid, client)
    AUTH_CLIENTS.pop(uid, None)

    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
        "auth_code",
    ):
        context.user_data.pop(key, None)

    if update.callback_query is None:
        await update.effective_message.reply_text(
            "✅ <b>Telegram account connected successfully.</b>\n"
            f"Account: {me.first_name or '-'} (@{me.username or '-'})\n"
            f"Telegram ID: <code>{me.id}</code>",
            parse_mode="HTML",
        )


async def _show_code_pad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data.get("auth_code", "")
    message = _code_message().format(code=_masked_code(code))
    query = update.callback_query

    if query:
        await query.edit_message_text(
            message,
            reply_markup=_otp_keyboard(),
            parse_mode="HTML",
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=message,
            reply_markup=_otp_keyboard(),
            parse_mode="HTML",
        )


async def lognum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Please use /lognum in the bot's private chat so login details are not exposed in a group."
        )
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "phone"
    context.user_data["auth_started_at"] = time.monotonic()

    if context.args:
        context.user_data["auth_phone"] = context.args[0].strip()
        await _begin_phone_login(update, context)
        return

    await update.effective_message.reply_text(
        "🔐 Send your Telegram phone number in international format.\n"
        "Example: +919876543210\n\n"
        "OTP and 2FA values are temporary only and are never stored.\n\n"
        "After Telegram sends the code, a 5-digit keypad will appear."
    )


async def begin_number_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Phone login is available only in the bot's private chat."
        )
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "phone"
    context.user_data["auth_started_at"] = time.monotonic()

    await update.callback_query.edit_message_text(
        "🔐 <b>Login with Number</b>\n\n"
        "Send your Telegram phone number in international format.\n"
        "Example: +919876543210\n\n"
        "Your OTP and 2FA password are temporary and are never stored.",
        parse_mode="HTML",
    )


async def _begin_phone_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    phone = context.user_data.get("auth_phone")
    if not phone:
        await update.effective_message.reply_text(
            "❌ Phone number is missing. Run /lognum again."
        )
        return

    client = TelegramClient(
        StringSession(),
        settings.api_id,
        settings.api_hash,
        connection_retries=2,
        request_retries=2,
        auto_reconnect=True,
    )

    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        AUTH_CLIENTS[uid] = client
        context.user_data["auth_phone_code_hash"] = sent.phone_code_hash
        context.user_data["auth_state"] = "code"
        context.user_data["auth_code"] = ""
        await _show_code_pad(update, context)
    except (
        OSError,
        ValueError,
        RuntimeError,
        PhoneNumberInvalidError,
        RPCError,
    ):
        await client.disconnect()
        await _clear_auth(uid, context)
        await update.effective_message.reply_text(
            "❌ Could not start Telegram phone login. Check the number/API configuration and try again."
        )


async def logsession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Please use /logsession in the bot's private chat."
        )
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "session"
    context.user_data["auth_started_at"] = time.monotonic()
    await update.effective_message.reply_text(
        "🔑 Send your existing authorized Telethon StringSession.\n"
        "It will be validated and encrypted before storage.\n\n"
        "⚠️ Send it only in this private chat."
    )


async def begin_session_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Session login is available only in the bot's private chat."
        )
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "session"
    context.user_data["auth_started_at"] = time.monotonic()

    await update.callback_query.edit_message_text(
        "🔑 <b>Login with Session</b>\n\n"
        "Send your existing authorized Telethon StringSession.\n"
        "It will be validated and encrypted before storage.\n\n"
        "⚠️ Send it only in this private chat.",
        parse_mode="HTML",
    )


async def auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    uid = query.from_user.id
    state = context.user_data.get("auth_state")

    if state != "code":
        await query.answer(
            "This login keypad is no longer active.",
            show_alert=True,
        )
        return

    await query.answer()

    if query.data == "auth:cancel":
        await _clear_auth(uid, context)
        await query.edit_message_text(
            "❌ Login cancelled. Temporary authentication state was cleared."
        )
        return

    if query.data == "auth:back":
        code = context.user_data.get("auth_code", "")
        context.user_data["auth_code"] = code[:-1]
        await _show_code_pad(update, context)
        return

    if query.data.startswith("auth:digit:"):
        digit = query.data.rsplit(":", 1)[-1]
        code = context.user_data.get("auth_code", "")

        if len(code) >= OTP_LENGTH:
            await query.answer(
                "The code already contains 5 digits. Press Submit.",
                show_alert=True,
            )
            return

        context.user_data["auth_code"] = code + digit
        await _show_code_pad(update, context)
        return

    if query.data == "auth:submit":
        code = context.user_data.get("auth_code", "")
        if len(code) != OTP_LENGTH or not code.isdigit():
            await query.answer(
                "Please enter exactly 5 digits.",
                show_alert=True,
            )
            return

        client = AUTH_CLIENTS.get(uid)
        if not client:
            await _clear_auth(uid, context)
            await query.edit_message_text(
                "❌ Login state expired. Please start /lognum again."
            )
            return

        phone = context.user_data.get("auth_phone")
        phone_code_hash = context.user_data.get("auth_phone_code_hash")

        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )
            await _save_authenticated_client(update, context, client)
            await query.edit_message_text(
                "✅ <b>Telegram account connected successfully.</b>",
                parse_mode="HTML",
            )
        except SessionPasswordNeededError:
            context.user_data["auth_state"] = "2fa"
            context.user_data.pop("auth_code", None)
            await query.edit_message_text(
                "🔐 <b>2-step verification is enabled.</b>\n\n"
                "Send the 2FA password in this private chat. It is used only in memory and never stored.",
                parse_mode="HTML",
            )
        except PhoneCodeInvalidError:
            context.user_data["auth_code"] = ""
            await query.answer(
                "Invalid code. Please enter the correct 5-digit code.",
                show_alert=True,
            )
            await _show_code_pad(update, context)
        except PhoneCodeExpiredError:
            await _clear_auth(uid, context)
            await query.edit_message_text(
                "⌛ The Telegram code expired. Please start /lognum again."
            )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel an active authentication flow or fall back to tag-task cancel."""
    if context.user_data.get("auth_state"):
        await _clear_auth(update.effective_user.id, context)
        await update.effective_message.reply_text(
            "❌ Login cancelled. Temporary authentication state was cleared."
        )
        return

    from handlers.tagall import cancel as cancel_tag_task

    await cancel_tag_task(update, context)


async def auth_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get("auth_state")
    if not state:
        return

    started = context.user_data.get("auth_started_at", time.monotonic())
    if time.monotonic() - started > settings.auth_timeout:
        await _clear_auth(uid, context)
        await update.effective_message.reply_text(
            "⏱️ Login session expired. Please run /lognum or /logsession again."
        )
        return

    value = update.effective_message.text.strip()

    if state == "phone":
        context.user_data["auth_phone"] = value
        await update.effective_message.delete()
        await _begin_phone_login(update, context)
        return

    if state == "session":
        try:
            client = await manager.connect_session(
                uid,
                value,
                settings.api_id,
                settings.api_hash,
            )
            await _save_authenticated_client(update, context, client)
            await update.effective_message.delete()
        except (AuthKeyUnregisteredError, ValueError):
            await update.effective_message.reply_text(
                "❌ The StringSession is invalid or unauthorized. Please try again."
            )
        return

    client = AUTH_CLIENTS.get(uid)
    if not client:
        await _clear_auth(uid, context)
        await update.effective_message.reply_text(
            "❌ Login state expired. Please run /lognum again."
        )
        return

    if state == "code":
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != OTP_LENGTH or not value.isdigit():
            await update.effective_message.reply_text(
                "❌ The Telegram login code must contain exactly 5 digits. Use the keypad shown above."
            )
            return
        context.user_data["auth_code"] = digits
        await _show_code_pad(update, context)
        await update.effective_message.delete()
        return

    if state == "2fa":
        try:
            await client.sign_in(password=value)
            await _save_authenticated_client(update, context, client)
            await update.effective_message.delete()
        except (ValueError, RuntimeError, OSError):
            await update.effective_message.reply_text(
                "❌ 2FA authentication failed. Please restart /lognum."
            )
