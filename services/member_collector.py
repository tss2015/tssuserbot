from telethon.tl.types import User


async def eligible_members(client, chat, max_members):
    """Collect mentionable human members from a Telegram chat.

    `chat` may be a raw Telegram chat ID or a python-telegram-bot Chat object.
    Telethon resolves the ID to its own entity before iterating participants.
    """
    chat_id = getattr(chat, "id", chat)
    entity = await client.get_entity(chat_id)

    result = []
    async for user in client.iter_participants(entity):
        if not isinstance(user, User):
            continue
        if user.bot or user.deleted or user.is_self:
            continue

        result.append(user)
        if len(result) >= max_members:
            break

    return result
