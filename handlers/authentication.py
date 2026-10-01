import time

from telegram import Update
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


async def _clear_auth(uid: int, context: ContextTypes.DEFAULT_TYPE):
    client = AUTH_CLIENTS.pop(uid, None)
    if client:
        await client.disconnect()
    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
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

    # The session is encrypted at rest. OTP and 2FA values never reach MongoDB.
    await db.users.update_one(
        {"bot_user_id": uid},
        {"$set": {
            "bot_user_id": uid,
            "telegram_user_id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "authenticated": True,
            "encrypted_session": encrypted,
        }},
        upsert=True,
    )
    await manager.attach_client(uid, client)
    AUTH_CLIENTS.pop(uid, None)
    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
    ):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        f"✅ Telegram account connected successfully.\n"
        f"Account: {me.first_name or '-'} (@{me.username or '-'})\n"
        f"Telegram ID: {me.id}"
    )


async def lognum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔐 Please use /lognum in the bot's private chat so login details are not exposed in a group.")
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "phone"
    context.user_data["auth_started_at"] = time.monotonic()
    if context.args:
        context.user_data["auth_phone"] = context.args[0].strip()
        await _begin_phone_login(update, context)
        return

    await update.message.reply_text(
        "🔐 Send your Telegram phone number in international format.\n"
        "Example: +919876543210\n\n"
        "OTP and 2FA values are temporary only and are never stored."
    )


async def _begin_phone_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    phone = context.user_data.get("auth_phone")
    if not phone:
        await update.message.reply_text("❌ Phone number is missing. Run /lognum again.")
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
        await update.message.reply_text(
            "📨 Telegram sent a login code. Send the code here.\n"
            "It is used only in memory and is never stored."
        )
    except (OSError, ValueError, RuntimeError, PhoneNumberInvalidError, RPCError):
        await client.disconnect()
        await _clear_auth(uid, context)
        await update.message.reply_text(
            "❌ Could not start Telegram phone login. Check the number/API configuration and try again."
        )


async def logsession(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔐 Please use /logsession in the bot's private chat.")
        return

    await _clear_auth(update.effective_user.id, context)
    context.user_data["auth_state"] = "session"
    context.user_data["auth_started_at"] = time.monotonic()
    await update.message.reply_text(
        "🔑 Send your existing authorized Telethon StringSession.\n"
        "It will be validated and encrypted before storage."
    )


async def auth_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = context.user_data.get("auth_state")
    if not state:
        return

    started = context.user_data.get("auth_started_at", time.monotonic())
    if time.monotonic() - started > settings.auth_timeout:
        await _clear_auth(uid, context)
        await update.message.reply_text("⏱️ Login session expired. Please run /lognum or /logsession again.")
        return

    value = update.message.text.strip()

    if state == "session":
        try:
            client = await manager.connect_session(
                uid,
                value,
                settings.api_id,
                settings.api_hash,
            )
            await _save_authenticated_client(update, context, client)
            await update.message.delete()
        except (AuthKeyUnregisteredError, ValueError):
            await update.message.reply_text(
                "❌ The StringSession is invalid or unauthorized. Please try again."
            )
        return

    client = AUTH_CLIENTS.get(uid)
    if not client:
        await _clear_auth(uid, context)
        await update.message.reply_text("❌ Login state expired. Please run /lognum again.")
        return

    if state == "code":
        phone = context.user_data.get("auth_phone")
        phone_code_hash = context.user_data.get("auth_phone_code_hash")
        try:
            await client.sign_in(
                phone=phone,
                code=value,
                phone_code_hash=phone_code_hash,
            )
            await _save_authenticated_client(update, context, client)
            await update.message.delete()
        except SessionPasswordNeededError:
            context.user_data["auth_state"] = "2fa"
            await update.message.reply_text(
                "🔐 This Telegram account has 2-step verification enabled.\n"
                "Send the 2FA password. It will be used only in memory and never stored."
            )
        except (PhoneCodeInvalidError, PhoneCodeExpiredError):
            await update.message.reply_text("❌ Invalid or expired Telegram code. Run /lognum again.")
        return

    if state == "2fa":
        try:
            await client.sign_in(password=value)
            await _save_authenticated_client(update, context, client)
            await update.message.delete()
        except (ValueError, RuntimeError, OSError):
            await update.message.reply_text("❌ 2FA authentication failed. Please restart /lognum.")
