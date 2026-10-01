import asyncio

from telethon import TelegramClient
from telethon.errors import AuthKeyUnregisteredError, RPCError
from telethon.sessions import StringSession


class TelegramClientManager:
    def __init__(self):
        self.clients = {}
        self.locks = {}

    def lock_for(self, bot_user_id):
        return self.locks.setdefault(bot_user_id, asyncio.Lock())

    async def disconnect(self, bot_user_id):
        client = self.clients.pop(bot_user_id, None)
        if client:
            await client.disconnect()

    async def connect_session(self, bot_user_id, session_string, api_id, api_hash):
        async with self.lock_for(bot_user_id):
            old = self.clients.get(bot_user_id)
            if old:
                await old.disconnect()

            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash,
                connection_retries=2,
                request_retries=2,
                auto_reconnect=True,
            )
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                raise ValueError("Session is not authorized.")

            self.clients[bot_user_id] = client
            return client

    async def attach_client(self, bot_user_id, client):
        async with self.lock_for(bot_user_id):
            old = self.clients.get(bot_user_id)
            if old and old is not client:
                await old.disconnect()
            self.clients[bot_user_id] = client
            return client

    async def reconnect_all(self, records, session_manager, api_id, api_hash):
        for record in records:
            try:
                session = session_manager.decrypt(record["encrypted_session"])
                await self.connect_session(
                    record["bot_user_id"], session, api_id, api_hash
                )
            except (AuthKeyUnregisteredError, RPCError, ValueError, OSError):
                # Recovery should not stop other users from reconnecting.
                continue


manager = TelegramClientManager()
