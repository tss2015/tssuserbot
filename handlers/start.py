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
        f"🔐 <b>Account Status</b>",
        f"{status_text}",
        "",
        f"👤 <b>User</b>",
        f"{html.escape(str(user_display))}",
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

    # Login is deliberately only surfaced in private chat.
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
                        callback_data="logout:yes",
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
    else:
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
                        callback_data="logout:yes",
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
