from motor.motor_asyncio import AsyncIOMotorClient

from config import settings


class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.users = None
        self.tasks = None
        self.events = None
        self.moods = None

    async def connect(self):
        self.client = AsyncIOMotorClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

        await self.client.admin.command("ping")

        self.db = self.client[settings.database_name]

        self.users = self.db.users
        self.tasks = self.db.tasks
        self.events = self.db.events
        self.moods = self.db.moods

        # Remove old bot_user_id indexes
        indexes = await self.users.list_indexes().to_list(length=None)

        for index in indexes:
            if index.get("key") == {"bot_user_id": 1}:
                await self.users.drop_index(index["name"])

        # Unique bot_user_id only for valid positive IDs
        await self.users.create_index(
            "bot_user_id",
            name="bot_user_id_unique",
            unique=True,
            partialFilterExpression={
                "bot_user_id": {
                    "$gt": 0,
                }
            },
        )

        # Remove old telegram_user_id indexes
        indexes = await self.users.list_indexes().to_list(length=None)

        for index in indexes:
            if index.get("key") == {"telegram_user_id": 1}:
                await self.users.drop_index(index["name"])

        # Recreate with a fixed name
        await self.users.create_index(
            "telegram_user_id",
            name="telegram_user_id_sparse",
            sparse=True,
        )

        await self.tasks.create_index(
            [("bot_user_id", 1), ("created_at", -1)]
        )

        await self.tasks.create_index(
            [("status", 1), ("created_at", -1)]
        )

        await self.events.create_index(
            [("created_at", -1)]
        )

        await self.moods.create_index(
            "scope",
            unique=True,
        )

    async def close(self):
        if self.client:
            self.client.close()

    async def log_event(
        self,
        name: str,
        bot_user_id=None,
        **fields,
    ):
        from utils.helpers import utcnow

        doc = {
            "name": name,
            "bot_user_id": bot_user_id,
            "fields": fields,
            "created_at": utcnow(),
        }

        await self.events.insert_one(doc)


db = Database()
