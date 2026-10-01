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

    async def _reset_index_by_key(self, collection, key, *, name, **options):
        """Drop any existing index with this key, then recreate it deterministically."""
        indexes = await collection.list_indexes().to_list(length=None)

        for index in indexes:
            if index.get("key") == key:
                existing_name = index.get("name")

                # Never attempt to drop MongoDB's mandatory _id index.
                if existing_name != "_id":
                    await collection.drop_index(existing_name)

        await collection.create_index(
            key,
            name=name,
            **options,
        )

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

        # USERS
        await self._reset_index_by_key(
            self.users,
            {"bot_user_id": 1},
            name="bot_user_id_unique",
            unique=True,
            partialFilterExpression={
                "bot_user_id": {
                    "$gt": 0,
                }
            },
        )

        await self._reset_index_by_key(
            self.users,
            {"telegram_user_id": 1},
            name="telegram_user_id_sparse",
            sparse=True,
        )

        # TASKS
        await self._reset_index_by_key(
            self.tasks,
            {"bot_user_id": 1, "created_at": -1},
            name="bot_user_id_created_at",
        )

        await self._reset_index_by_key(
            self.tasks,
            {"status": 1, "created_at": -1},
            name="status_created_at",
        )

        # EVENTS
        await self._reset_index_by_key(
            self.events,
            {"created_at": -1},
            name="created_at_desc",
        )

        # MOODS
        await self._reset_index_by_key(
            self.moods,
            {"scope": 1},
            name="scope_unique",
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
