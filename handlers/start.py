from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db


def _main_menu_keyboard(private: bool = True):
    if private:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔐 Login with Number",
                        callback_data="auth:lognum",
                    ),
                    InlineKeyboardButton(
                        "🔑 Login with Session",
                        callback_data="auth:logsession",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📊 Status",
                        callback_data="menu:status",
                    ),
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data="menu:settings",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📜 History",
                        callback_data="menu:history",
                    ),
                    InlineKeyboardButton(
                        "🚪 Logout",
                        callback_data="logout:confirm",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❓ Help",
                        callback_data="menu:help",
                    ),
                ],
            ]
        )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 Tag All",
                    callback_data="menu:tagall",
                ),
            ],
            [
                InlineKeyboardButton(
                    "😊 Happy",
                    callback_data="menu:tgallhappy",
                ),
                InlineKeyboardButton(
                    "😎 Sassy",
                    callback_data="menu:tgallsassy",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🥺 Sulky",
                    callback_data="menu:tgallsulky",
                ),
                InlineKeyboardButton(
                    "❤️ Romantic",
                    callback_data="menu:tgallromantic",
                ),
            ],
            [
                InlineKeyboardButton(
                    "😴 Sleepy",
                    callback_data="menu:tgallsleepy",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="menu:cancel",
                ),
            ],
        ]
    )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user:
        return

    if not update.effective_chat:
        return

    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    if chat_type == "private":
        record = await db.users.find_one(
            {"bot_user_id": user_id}
        )

        connected = bool(record)

        if connected:
            account_status = "🟢 Connected"
        else:
            account_status = "🔴 Not connected"

        text = (
            "🤖 <b>Telegram Userbot Manager</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> "
            f"{update.effective_user.first_name or 'User'}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"🔐 <b>Account:</b> {account_status}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ <b>Available Features</b>\n\n"
            "🔐 Login with Number\n"
            "🔑 Login with StringSession\n"
            "📊 Account Status\n"
            "⚙️ Settings\n"
            "📜 Task History\n"
            "🚪 Logout\n\n"
            "Use the buttons below or the available commands."
        )

        await update.effective_message.reply_text(
            text,
            reply_markup=_main_menu_keyboard(
                private=True
            ),
            parse_mode="HTML",
        )

        return

    # ---------------------------------------------------------
    # GROUP START
    # ---------------------------------------------------------

    text = (
        "🤖 <b>Telegram Userbot Manager</b>\n\n"
        "📢 <b>Group Tagging</b>\n\n"
        "Use the tagging commands below.\n\n"
        "• <code>/tagall</code>\n"
        "• <code>/tagall romantic</code>\n"
        "• <code>/tagmood romantic</code>\n"
        "• <code>/tgallhappy</code>\n"
        "• <code>/tgallsassy</code>\n"
        "• <code>/tgallsulky</code>\n"
        "• <code>/tgallromantic</code>\n"
        "• <code>/tgallsleepy</code>\n"
        "• <code>/cancel</code>\n\n"
        "🔐 Login commands are available only in private chat."
    )

    await update.effective_message.reply_text(
        text,
        reply_markup=_main_menu_keyboard(
            private=False
        ),
        parse_mode="HTML",
    )


async def main_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle main-menu inline keyboard callbacks."""

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    # ---------------------------------------------------------
    # BACK
    # ---------------------------------------------------------

    if data == "menu:back":
        fake_update = update

        if fake_update.effective_chat:
            if fake_update.effective_chat.type == "private":
                await start(
                    fake_update,
                    context,
                )
            else:
                await start(
                    fake_update,
                    context,
                )

        return

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    if data == "menu:status":
        from handlers.account import status

        await status(
            update,
            context,
        )
        return

    # ---------------------------------------------------------
    # SETTINGS
    # ---------------------------------------------------------

    if data == "menu:settings":
        from handlers.settings import settings_command

        await settings_command(
            update,
            context,
        )
        return

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------

    if data == "menu:history":
        from handlers.history import history

        await history(
            update,
            context,
        )
        return

    # ---------------------------------------------------------
    # HELP
    # ---------------------------------------------------------

    if data == "menu:help":
        from handlers.help import help_command

        await help_command(
            update,
            context,
        )
        return

    # ---------------------------------------------------------
    # TAG ALL
    # ---------------------------------------------------------

    if data == "menu:tagall":
        await query.edit_message_text(
            "📢 <b>Tag All</b>\n\n"
            "Use:\n"
            "<code>/tagall your message</code>\n\n"
            "For example:\n"
            "<code>/tagall plz join vc</code>\n\n"
            "For mood tagging:\n"
            "<code>/tagall romantic</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="menu:back",
                        )
                    ]
                ]
            ),
        )
        return

    # ---------------------------------------------------------
    # MOOD SHORTCUTS
    # ---------------------------------------------------------

    mood_commands = {
        "menu:tgallhappy": "happy",
        "menu:tgallsassy": "sassy",
        "menu:tgallsulky": "sulky",
        "menu:tgallromantic": "romantic",
        "menu:tgallsleepy": "sleepy",
    }

    if data in mood_commands:
        mood = mood_commands[data]

        await query.edit_message_text(
            f"🎭 <b>{mood.title()} Tagging</b>\n\n"
            f"Use:\n"
            f"<code>/tgall{mood}</code>\n\n"
            "Each participant will receive a "
            "different AI-generated message.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="menu:back",
                        )
                    ]
                ]
            ),
        )
        return

    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

    if data == "menu:cancel":
        from handlers.tagall import cancel

        await cancel(
            update,
            context,
        )
        return
