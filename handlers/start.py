from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import db


# ============================================================
# MAIN MENU
# ============================================================

def _main_menu_keyboard(
    authenticated: bool,
) -> InlineKeyboardMarkup:
    keyboard = []

    # --------------------------------------------------------
    # Account section
    # --------------------------------------------------------

    if authenticated:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📊 Account Status",
                    callback_data="menu:status",
                ),
                InlineKeyboardButton(
                    "⚙️ Settings",
                    callback_data="menu:settings",
                ),
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "📜 History",
                    callback_data="menu:history",
                ),
                InlineKeyboardButton(
                    "🚪 Logout",
                    callback_data="logout:ask",
                ),
            ]
        )

    else:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📱 Login with Number",
                    callback_data="auth:lognum",
                )
            ]
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔑 Login with Session",
                    callback_data="auth:logsession",
                )
            ]
        )

    # --------------------------------------------------------
    # Help
    # --------------------------------------------------------

    keyboard.append(
        [
            InlineKeyboardButton(
                "❓ Help",
                callback_data="menu:help",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if not user:
        return

    # --------------------------------------------------------
    # Start is intended for private account management.
    # --------------------------------------------------------

    if update.effective_chat.type != "private":
        await update.effective_message.reply_text(
            "ℹ️ Please open my private chat and use /start there."
        )
        return

    record = await db.users.find_one(
        {
            "bot_user_id": user.id,
            "authenticated": True,
        }
    )

    authenticated = bool(record)

    if authenticated:
        telegram_id = record.get(
            "telegram_user_id",
            "-",
        )

        username = record.get(
            "username"
        )

        account_name = (
            f"@{username}"
            if username
            else record.get(
                "first_name",
                "Connected account",
            )
        )

        text = (
            "🤖 <b>Telegram Userbot Manager</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>Account:</b> Connected\n"
            f"👤 <b>User:</b> {account_name}\n"
            f"🆔 <b>ID:</b> <code>{telegram_id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Choose an option below."
        )

    else:
        text = (
            "🤖 <b>Telegram Userbot Manager</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔐 <b>Account:</b> Not connected\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📱 Login with your Telegram number or\n"
            "🔑 provide an existing Telethon StringSession.\n\n"
            "Choose an option below."
        )

    await update.effective_message.reply_text(
        text,
        reply_markup=_main_menu_keyboard(authenticated),
        parse_mode="HTML",
    )


# ============================================================
# MAIN MENU CALLBACK
# ============================================================

async def main_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    uid = query.from_user.id
    data = query.data or ""

    # --------------------------------------------------------
    # Login buttons
    #
    # Normally these are handled directly by authentication.py,
    # but these compatibility branches allow old callback data.
    # --------------------------------------------------------

    if data == "login:number":
        from handlers.authentication import begin_number_button

        await begin_number_button(
            update,
            context,
        )
        return

    if data == "login:session":
        from handlers.authentication import begin_session_button

        await begin_session_button(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # Account status
    # --------------------------------------------------------

    if data in (
        "menu:status",
        "account:status",
        "status",
    ):
        record = await db.users.find_one(
            {
                "bot_user_id": uid,
            }
        )

        if not record or not record.get("authenticated"):
            await query.edit_message_text(
                "❌ <b>No Telegram account is linked.</b>\n\n"
                "Use the Login buttons below to connect one.",
                reply_markup=_main_menu_keyboard(False),
                parse_mode="HTML",
            )
            return

        username = record.get("username")
        first_name = record.get("first_name") or "-"
        telegram_id = record.get("telegram_user_id") or "-"

        account = (
            f"@{username}"
            if username
            else first_name
        )

        await query.edit_message_text(
            "📊 <b>Account Status</b>\n\n"
            f"👤 Account: {account}\n"
            f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
            "🔐 Status: <b>Connected</b>",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Back",
                            callback_data="back:menu",
                        )
                    ]
                ]
            ),
            parse_mode="HTML",
        )
        return

    # --------------------------------------------------------
    # Settings
    # --------------------------------------------------------

    if data in (
        "menu:settings",
        "settings",
    ):
        # Preserve the existing settings handler.
        from handlers.settings import settings_command

        fake_update = update

        await settings_command(
            fake_update,
            context,
        )
        return

    # --------------------------------------------------------
    # History
    # --------------------------------------------------------

    if data in (
        "menu:history",
        "history",
    ):
        from handlers.history import history

        await history(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # Help
    # --------------------------------------------------------

    if data in (
        "menu:help",
        "help",
    ):
        from handlers.help import help_command

        await help_command(
            update,
            context,
        )
        return

    # --------------------------------------------------------
    # Tagging buttons
    #
    # These are kept for compatibility with existing start menus.
    # --------------------------------------------------------

    if data.startswith("menu:"):
        command = data.split(":", 1)[1]

        command_map = {
            "tagall": "/tagall",
            "tgallhappy": "/tgallhappy",
            "tgallsassy": "/tgallsassy",
            "tgallsulky": "/tgallsulky",
            "tgallromantic": "/tgallromantic",
            "tgallsleepy": "/tgallsleepy",
            "cancel": "/cancel",
        }

        if command in command_map:
            await query.edit_message_text(
                f"ℹ️ Use <code>{command_map[command]}</code> in the group.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅️ Back",
                                callback_data="back:menu",
                            )
                        ]
                    ]
                ),
            )
            return

    # --------------------------------------------------------
    # Back to menu
    # --------------------------------------------------------

    if data in (
        "back:menu",
        "menu:back",
    ):
        record = await db.users.find_one(
            {
                "bot_user_id": uid,
                "authenticated": True,
            }
        )

        await query.edit_message_text(
            "🤖 <b>Telegram Userbot Manager</b>\n\n"
            "Choose an option below.",
            reply_markup=_main_menu_keyboard(
                bool(record)
            ),
            parse_mode="HTML",
        )
        return
