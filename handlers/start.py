import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    record = await db.users.find_one({"bot_user_id": user.id}) or {}

    connected = bool(record.get("authenticated"))
    status_text = "🟢 Connected" if connected else "🔴 Not Connected"

    username = record.get("username") or user.username
    first_name = record.get("first_name") or user.first_name or "User"

    if username:
        user_display = f"@{username.lstrip('@')}"
    else:
        user_display = first_name

    telegram_user_id = record.get("telegram_user_id")
    if telegram_user_id is None:
        telegram_user_id = "Not linked"

    lines = [
        "🤖 <b>Telegram Userbot Manager</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "🔐 <b>Account Status</b>",
        status_text,
        "",
        "👤 <b>User</b>",
        html.escape(str(user_display)),
        "",
        "🆔 <b>Telegram ID</b>",
        f"<code>{html.escape(str(telegram_user_id))}</code>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "✨ <b>Features</b>",
        "📢 Safe member tagging",
        "📊 Account & task status",
        "⚙️ Per-user settings",
        "📜 Task history",
        "🔐 Encrypted sessions",
        "🛡️ Flood/rate-limit protection",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📖 <b>Commands</b>",
        "",
        "<b>🏠 General</b>",
        "/start — Open this menu",
        "/help — Show help and commands",
        "/status — Account status",
        "/history — Task history",
        "/settings — Personal settings",
        "/logout — Logout your account",
        "",
    ]

    keyboard = []

    # Login buttons are only shown in private chat.
    if chat and chat.type == "private":
        lines.extend(
            [
                "<b>🔐 Login</b>",
                "/lognum — Login using phone number",
                "/logsession — Login using StringSession",
                "",
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "📱 Login with Number",
                    callback_data="login:number",
                ),
                InlineKeyboardButton(
                    "🔑 Login with Session",
                    callback_data="login:session",
                ),
            ]
        )

    lines.extend(
        [
            "<b>📢 Tagging</b>",
            "/tagall — Tag members using the selected/automatic mood",
            "/tagmood &lt;mood&gt; — Tag with a selected mood",
            "/tgallhappy — Happy tagging",
            "/tgallsassy — Sassy tagging",
            "/tgallsulky — Sulky tagging",
            "/tgallromantic — Romantic tagging",
            "/tgallsleepy — Sleepy tagging",
            "/cancel — Cancel active tagging",
            "",
            "<b>🎭 Mood</b>",
            "/mood — Show current mood",
            "/setmood — Change mood",
            "/randommood — Random mood",
            "/game — Mood game",
            "/gm — Good morning",
            "/gn — Good night",
            "",
            "<b>👑 Admin</b>",
            "/admin — Admin panel",
            "/stats — Bot statistics",
            "/users — User list",
            "/tasks — Task list",
            "/broadcast — Broadcast message",
            "/maintenance — Maintenance mode",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "💡 <b>Tip:</b> Use the buttons where available or type commands manually.",
        ]
    )

    if chat and chat.type == "private":
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        "📊 Account Status",
                        callback_data="account:status",
                    ),
                    InlineKeyboardButton(
                        "📜 Task History",
                        callback_data="history",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data="settings",
                    ),
                    InlineKeyboardButton(
                        "🚪 Logout",
                        callback_data="logout:ask",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❓ Help & Commands",
                        callback_data="help",
                    )
                ],
            ]
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _send_or_edit(
    update: Update,
    text: str,
    reply_markup=None,
    parse_mode=None,
):
    query = update.callback_query

    if query:
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )


async def main_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "login:number":
        from handlers.authentication import begin_number_button

        await begin_number_button(update, context)
        return

    if data == "login:session":
        from handlers.authentication import begin_session_button

        await begin_session_button(update, context)
        return

    if data == "account:status":
        from handlers.account import status_callback

        await status_callback(update, context)
        return

    if data == "history":
        from handlers.history import history_callback

        await history_callback(update, context)
        return

    if data == "settings":
        from handlers.settings import settings_callback_open

        await settings_callback_open(update, context)
        return

    if data == "help":
        from handlers.help import help_callback

        await help_callback(update, context)
        return

    if data == "back:menu":
        await start(update, context)
        await query.delete_message()
        return

    await _send_or_edit(update, "❌ Unknown menu action.")
