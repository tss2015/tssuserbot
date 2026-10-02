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


# ============================================================
# SESSION MANAGER
# ============================================================

session_manager = SessionManager(
    settings.session_encryption_key
)


# ============================================================
# TEMPORARY AUTH CLIENTS
#
# These exist only while /lognum authentication is running.
# ============================================================

AUTH_CLIENTS: dict[int, TelegramClient] = {}

OTP_LENGTH = 5


# ============================================================
# OTP KEYBOARD
# ============================================================

def _otp_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "1",
                callback_data="auth:digit:1",
            ),
            InlineKeyboardButton(
                "2",
                callback_data="auth:digit:2",
            ),
            InlineKeyboardButton(
                "3",
                callback_data="auth:digit:3",
            ),
        ],
        [
            InlineKeyboardButton(
                "4",
                callback_data="auth:digit:4",
            ),
            InlineKeyboardButton(
                "5",
                callback_data="auth:digit:5",
            ),
            InlineKeyboardButton(
                "6",
                callback_data="auth:digit:6",
            ),
        ],
        [
            InlineKeyboardButton(
                "7",
                callback_data="auth:digit:7",
            ),
            InlineKeyboardButton(
                "8",
                callback_data="auth:digit:8",
            ),
            InlineKeyboardButton(
                "9",
                callback_data="auth:digit:9",
            ),
        ],
        [
            InlineKeyboardButton(
                "↩️ Back",
                callback_data="auth:back",
            ),
            InlineKeyboardButton(
                "0",
                callback_data="auth:digit:0",
            ),
            InlineKeyboardButton(
                "✅ Submit",
                callback_data="auth:submit",
            ),
        ],
        [
            InlineKeyboardButton(
                "❌ Cancel Login",
                callback_data="auth:cancel",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# OTP DISPLAY
# ============================================================

def _masked_code(code: str) -> str:
    return (
        "".join("●" for _ in code)
        + "○" * max(
            0,
            OTP_LENGTH - len(code),
        )
    )


def _code_message() -> str:
    return (
        "📨 <b>Telegram just sent a login code</b>.\n\n"
        "Enter the 5-digit code using the keypad below.\n\n"
        "🔐 <b>Code:</b> <code>{code}</code>\n\n"
        "Use /cancel at any time to stop the login process."
    )


# ============================================================
# CLEAR AUTH STATE
# ============================================================

async def _clear_auth(
    uid: int,
    context: ContextTypes.DEFAULT_TYPE,
):
    client = AUTH_CLIENTS.pop(uid, None)

    if client:
        try:
            await client.disconnect()
        except (OSError, RPCError):
            pass

    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
        "auth_code",
    ):
        context.user_data.pop(key, None)


# ============================================================
# SAVE AUTHENTICATED CLIENT
# ============================================================

async def _save_authenticated_client(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client: TelegramClient,
):
    """
    Permanently associate the newly authenticated Telegram
    account with the Telegram user who is using this control bot.

    bot_user_id:
        ID of the user talking to the control bot.

    telegram_user_id:
        ID of the Telegram account that was just logged in.
    """

    uid = update.effective_user.id

    # --------------------------------------------------------
    # Make absolutely sure the Telethon client is authorized.
    # --------------------------------------------------------

    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram client is not authorized."
        )

    # --------------------------------------------------------
    # Get the newly authenticated Telegram account.
    # --------------------------------------------------------

    me = await client.get_me()

    if not me or not me.id:
        raise RuntimeError(
            "Unable to retrieve authenticated Telegram account."
        )

    # --------------------------------------------------------
    # Export the StringSession.
    # --------------------------------------------------------

    session = client.session.save()

    if not session:
        raise RuntimeError(
            "Unable to export Telegram StringSession."
        )

    # --------------------------------------------------------
    # Encrypt session before MongoDB storage.
    # --------------------------------------------------------

    encrypted = session_manager.encrypt(
        session
    )

    # --------------------------------------------------------
    # Store using the CONTROL BOT USER ID.
    #
    # This is critical:
    #
    # User A -> Control bot -> User A's Telegram account
    #
    # Therefore:
    #
    # bot_user_id = control bot user's Telegram ID
    # telegram_user_id = logged-in Telegram account ID
    # --------------------------------------------------------

    await db.users.update_one(
        {
            "bot_user_id": uid,
        },
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

    # --------------------------------------------------------
    # Immediately attach the same authorized client to manager.
    #
    # This makes the newly logged-in account usable without
    # waiting for the next reconnect cycle.
    # --------------------------------------------------------

    await manager.attach_client(
        uid,
        client,
    )

    # --------------------------------------------------------
    # Verify the database record actually exists.
    # --------------------------------------------------------

    saved = await db.users.find_one(
        {
            "bot_user_id": uid,
            "authenticated": True,
            "telegram_user_id": me.id,
        }
    )

    if not saved:
        raise RuntimeError(
            "Telegram account authenticated, but the account "
            "could not be linked to the control-bot user."
        )

    # --------------------------------------------------------
    # Remove temporary authentication state.
    # --------------------------------------------------------

    AUTH_CLIENTS.pop(
        uid,
        None,
    )

    for key in (
        "auth_state",
        "auth_phone",
        "auth_phone_code_hash",
        "auth_started_at",
        "auth_code",
    ):
        context.user_data.pop(
            key,
            None,
        )

    return me


# ============================================================
# SHOW OTP PAD
# ============================================================

async def _show_code_pad(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    code = context.user_data.get(
        "auth_code",
        "",
    )

    message = _code_message().format(
        code=_masked_code(code)
    )

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


# ============================================================
# PHONE LOGIN START
# ============================================================

async def _begin_phone_login(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    uid = update.effective_user.id

    phone = context.user_data.get(
        "auth_phone"
    )

    if not phone:
        await update.effective_message.reply_text(
            "❌ Phone number is missing. Please start /lognum again."
        )
        return

    # --------------------------------------------------------
    # Remove previous temporary client for this user.
    # --------------------------------------------------------

    old = AUTH_CLIENTS.pop(
        uid,
        None,
    )

    if old:
        try:
            await old.disconnect()
        except (OSError, RPCError):
            pass

    # --------------------------------------------------------
    # Create fresh Telethon StringSession client.
    # --------------------------------------------------------

    client = TelegramClient(
        StringSession(),
        settings.api_id,
        settings.api_hash,
        device_model="Telegram Userbot Manager",
        system_version="Linux",
        app_version="1.0",
    )

    try:
        await client.connect()

        result = await client.send_code_request(
            phone
        )

        AUTH_CLIENTS[uid] = client

        context.user_data[
            "auth_phone_code_hash"
        ] = result.phone_code_hash

        context.user_data[
            "auth_state"
        ] = "code"

        context.user_data[
            "auth_started_at"
        ] = time.monotonic()

        context.user_data[
            "auth_code"
        ] = ""

        await _show_code_pad(
            update,
            context,
        )

    except PhoneNumberInvalidError:
        await _clear_auth(
            uid,
            context,
        )

        await update.effective_message.reply_text(
            "❌ Invalid Telegram phone number."
        )

    except (RPCError, OSError):
        await _clear_auth(
            uid,
            context,
        )

        await update.effective_message.reply_text(
            "❌ Telegram could not send the login code. "
            "Please check the number and try again."
        )


# ============================================================
# LOGIN WITH NUMBER BUTTON
# ============================================================

async def begin_number_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    if update.effective_chat.type != "private":
        await query.answer(
            "Please use login in private chat.",
            show_alert=True,
        )
        return

    await _clear_auth(
        update.effective_user.id,
        context,
    )

    context.user_data[
        "auth_state"
    ] = "phone"

    context.user_data[
        "auth_started_at"
    ] = time.monotonic()

    await query.edit_message_text(
        "📱 <b>Login with Phone Number</b>\n\n"
        "Send your Telegram phone number in international format.\n\n"
        "Example:\n"
        "<code>+919876543210</code>\n\n"
        "⚠️ Send it only in this private chat.",
        parse_mode="HTML",
    )


# ============================================================
# LOGIN WITH SESSION BUTTON
# ============================================================

async def begin_session_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    if update.effective_chat.type != "private":
        await query.answer(
            "Please use login in private chat.",
            show_alert=True,
        )
        return

    await _clear_auth(
        update.effective_user.id,
        context,
    )

    context.user_data[
        "auth_state"
    ] = "session"

    context.user_data[
        "auth_started_at"
    ] = time.monotonic()

    await query.edit_message_text(
        "🔑 <b>Login with StringSession</b>\n\n"
        "Send your existing authorized Telethon "
        "StringSession.\n\n"
        "It will be validated and encrypted before storage.\n\n"
        "⚠️ Send it only in this private chat.",
        parse_mode="HTML",
    )


# ============================================================
# /LOGNUM
# ============================================================

async def lognum(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Please use /lognum in my private chat "
            "so login details are not exposed in a group."
        )
        return

    await _clear_auth(
        update.effective_user.id,
        context,
    )

    context.user_data[
        "auth_state"
    ] = "phone"

    context.user_data[
        "auth_started_at"
    ] = time.monotonic()

    await update.effective_message.reply_text(
        "📱 <b>Login with Phone Number</b>\n\n"
        "Send your Telegram phone number in international format.\n\n"
        "Example:\n"
        "<code>+919876543210</code>\n\n"
        "⚠️ Send it only in this private chat.",
        parse_mode="HTML",
    )


# ============================================================
# /LOGSESSION
# ============================================================

async def logsession(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "🔐 Please use /logsession in my private chat."
        )
        return

    await _clear_auth(
        update.effective_user.id,
        context,
    )

    context.user_data[
        "auth_state"
    ] = "session"

    context.user_data[
        "auth_started_at"
    ] = time.monotonic()

    await update.effective_message.reply_text(
        "🔑 <b>Login with StringSession</b>\n\n"
        "Send your existing Telethon StringSession.\n\n"
        "⚠️ Send it only in this private chat.",
        parse_mode="HTML",
    )


# ============================================================
# AUTH CALLBACK
# ============================================================

async def auth_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    uid = query.from_user.id
    state = context.user_data.get(
        "auth_state"
    )

    # --------------------------------------------------------
    # Login button callbacks
    # --------------------------------------------------------

    if query.data == "auth:lognum":
        await begin_number_button(
            update,
            context,
        )
        return

    if query.data == "auth:logsession":
        await begin_session_button(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # OTP state check
    # --------------------------------------------------------

    if state != "code":
        await query.answer(
            "This login keypad is no longer active.",
            show_alert=True,
        )
        return

    await query.answer()

    # --------------------------------------------------------
    # Cancel
    # --------------------------------------------------------

    if query.data == "auth:cancel":
        await _clear_auth(
            uid,
            context,
        )

        await query.edit_message_text(
            "❌ Login cancelled.\n"
            "Temporary authentication state was cleared."
        )
        return

    # --------------------------------------------------------
    # Backspace
    # --------------------------------------------------------

    if query.data == "auth:back":
        code = context.user_data.get(
            "auth_code",
            "",
        )

        context.user_data[
            "auth_code"
        ] = code[:-1]

        await _show_code_pad(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # Digit
    # --------------------------------------------------------

    if query.data.startswith(
        "auth:digit:"
    ):
        digit = query.data.rsplit(
            ":",
            1,
        )[-1]

        code = context.user_data.get(
            "auth_code",
            "",
        )

        if len(code) >= OTP_LENGTH:
            await query.answer(
                "The code already contains 5 digits. Press Submit.",
                show_alert=True,
            )
            return

        context.user_data[
            "auth_code"
        ] = code + digit

        await _show_code_pad(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # Submit
    # --------------------------------------------------------

    if query.data == "auth:submit":
        code = context.user_data.get(
            "auth_code",
            "",
        )

        if (
            len(code) != OTP_LENGTH
            or not code.isdigit()
        ):
            await query.answer(
                "Please enter exactly 5 digits.",
                show_alert=True,
            )
            return

        client = AUTH_CLIENTS.get(
            uid
        )

        if not client:
            await _clear_auth(
                uid,
                context,
            )

            await query.edit_message_text(
                "❌ Login state expired.\n\n"
                "Please start /lognum again."
            )
            return

        phone = context.user_data.get(
            "auth_phone"
        )

        phone_code_hash = context.user_data.get(
            "auth_phone_code_hash"
        )

        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )

            me = await _save_authenticated_client(
                update,
                context,
                client,
            )

            await query.edit_message_text(
                "✅ <b>Telegram account connected successfully.</b>\n\n"
                f"👤 Account: "
                f"{me.first_name or '-'}\n"
                f"🆔 Telegram ID: "
                f"<code>{me.id}</code>",
                parse_mode="HTML",
            )

        except SessionPasswordNeededError:
            context.user_data[
                "auth_state"
            ] = "2fa"

            context.user_data.pop(
                "auth_code",
                None,
            )

            await query.edit_message_text(
                "🔐 <b>2-step verification is enabled.</b>\n\n"
                "Send the 2FA password in this private chat.\n\n"
                "The password is used only in memory "
                "and is never stored.",
                parse_mode="HTML",
            )

        except PhoneCodeInvalidError:
            context.user_data[
                "auth_code"
            ] = ""

            await query.answer(
                "Invalid code. Please enter the correct 5-digit code.",
                show_alert=True,
            )

            await _show_code_pad(
                update,
                context,
            )

        except PhoneCodeExpiredError:
            await _clear_auth(
                uid,
                context,
            )

            await query.edit_message_text(
                "⌛ The Telegram code expired.\n\n"
                "Please start /lognum again."
            )

        except (RPCError, OSError, RuntimeError):
            await _clear_auth(
                uid,
                context,
            )

            await query.edit_message_text(
                "❌ Telegram authentication failed.\n\n"
                "Please start /lognum again."
            )


# ============================================================
# /CANCEL
# ============================================================

async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if context.user_data.get(
        "auth_state"
    ):
        await _clear_auth(
            update.effective_user.id,
            context,
        )

        await update.effective_message.reply_text(
            "❌ Login cancelled.\n"
            "Temporary authentication state was cleared."
        )
        return

    from handlers.tagall import cancel as cancel_tag_task

    await cancel_tag_task(
        update,
        context,
    )


# ============================================================
# TEXT AUTHENTICATION
# ============================================================

async def auth_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    uid = update.effective_user.id

    state = context.user_data.get(
        "auth_state"
    )

    if not state:
        return

    # --------------------------------------------------------
    # Timeout
    # --------------------------------------------------------

    started = context.user_data.get(
        "auth_started_at",
        time.monotonic(),
    )

    if (
        time.monotonic() - started
        > settings.auth_timeout
    ):
        await _clear_auth(
            uid,
            context,
        )

        await update.effective_message.reply_text(
            "⏱️ Login session expired.\n\n"
            "Please run /lognum or /logsession again."
        )
        return

    value = (
        update.effective_message.text
        or ""
    ).strip()

    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    if state == "phone":
        context.user_data[
            "auth_phone"
        ] = value

        try:
            await update.effective_message.delete()
        except (OSError, RPCError):
            pass

        await _begin_phone_login(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # STRING SESSION
    # --------------------------------------------------------

    if state == "session":
        try:
            client = await manager.connect_session(
                uid,
                value,
                settings.api_id,
                settings.api_hash,
            )

            me = await _save_authenticated_client(
                update,
                context,
                client,
            )

            try:
                await update.effective_message.delete()
            except (OSError, RPCError):
                pass

            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "✅ <b>Telegram account connected successfully.</b>\n\n"
                    f"👤 Account: {me.first_name or '-'}\n"
                    f"🆔 Telegram ID: <code>{me.id}</code>"
                ),
                parse_mode="HTML",
            )

        except (
            AuthKeyUnregisteredError,
            ValueError,
            RuntimeError,
        ):
            await update.effective_message.reply_text(
                "❌ The StringSession is invalid, "
                "unauthorized, or could not be linked."
            )

        return

    # --------------------------------------------------------
    # OTP CODE
    # --------------------------------------------------------

    if state == "code":
        digits = "".join(
            ch
            for ch in value
            if ch.isdigit()
        )

        if (
            len(digits) != OTP_LENGTH
            or not value.isdigit()
        ):
            await update.effective_message.reply_text(
                "❌ The Telegram login code must contain "
                "exactly 5 digits.\n\n"
                "Use the keypad shown above."
            )
            return

        context.user_data[
            "auth_code"
        ] = digits

        await _show_code_pad(
            update,
            context,
        )

        try:
            await update.effective_message.delete()
        except (OSError, RPCError):
            pass

        return

    # --------------------------------------------------------
    # AUTH CLIENT
    # --------------------------------------------------------

    client = AUTH_CLIENTS.get(
        uid
    )

    if not client:
        await _clear_auth(
            uid,
            context,
        )

        await update.effective_message.reply_text(
            "❌ Login state expired.\n\n"
            "Please run /lognum again."
        )
        return

    # --------------------------------------------------------
    # 2FA PASSWORD
    # --------------------------------------------------------

    if state == "2fa":
        try:
            await client.sign_in(
                password=value
            )

            me = await _save_authenticated_client(
                update,
                context,
                client,
            )

            try:
                await update.effective_message.delete()
            except (OSError, RPCError):
                pass

            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "✅ <b>Telegram account connected successfully.</b>\n\n"
                    f"👤 Account: {me.first_name or '-'}\n"
                    f"🆔 Telegram ID: <code>{me.id}</code>"
                ),
                parse_mode="HTML",
            )

        except (
            ValueError,
            RuntimeError,
            OSError,
            RPCError,
        ):
            await update.effective_message.reply_text(
                "❌ 2FA authentication failed.\n\n"
                "Please restart /lognum."
            )
