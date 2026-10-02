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

    async def _drop_indexes_for_key(self, collection, key_pattern):
        """
        Remove existing indexes using the specified key pattern.

        This prevents MongoDB IndexOptionsConflict errors when an
        existing index has the correct fields but a different name.
        """
        indexes = await collection.list_indexes().to_list(length=None)

        for index in indexes:
            name = index.get("name")
            key = index.get("key")

            # Never remove MongoDB's default _id index.
            if name == "_id_":
                continue

            if key == key_pattern:
                await collection.drop_index(name)

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

        # ============================================================
        # USERS
        # ============================================================

        # Remove obsolete indexes based on the old "user_id" field.
        await self._drop_indexes_for_key(
            self.users,
            {"user_id": 1},
        )

        # Recreate bot_user_id index safely.
        await self._drop_indexes_for_key(
            self.users,
            {"bot_user_id": 1},
        )

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

        # telegram_user_id is intentionally non-unique.
        await self._drop_indexes_for_key(
            self.users,
            {"telegram_user_id": 1},
        )

        await self.users.create_index(
            "telegram_user_id",
            name="telegram_user_id_sparse",
            sparse=True,
        )

        # ============================================================
        # TASKS
        # ============================================================

        await self._drop_indexes_for_key(
            self.tasks,
            {
                "bot_user_id": 1,
                "created_at": -1,
            },
        )

        await self.tasks.create_index(
            [
                ("bot_user_id", 1),
                ("created_at", -1),
            ],
            name="bot_user_id_created_at",
        )

        await self._drop_indexes_for_key(
            self.tasks,
            {
                "status": 1,
                "created_at": -1,
            },
        )

        await self.tasks.create_index(
            [
                ("status", 1),
                ("created_at", -1),
            ],
            name="status_created_at",
        )

        # ============================================================
        # EVENTS
        # ============================================================

        # This specifically fixes:
        #
        # Index already exists with a different name:
        # created_at_desc
        #
        await self._drop_indexes_for_key(
            self.events,
            {
                "created_at": -1,
            },
        )

        await self.events.create_index(
            [
                ("created_at", -1),
            ],
            name="events_created_at",
        )

        # ============================================================
        # MOODS
        # ============================================================

        await self._drop_indexes_for_key(
            self.moods,
            {
                "scope": 1,
            },
        )

        await self.moods.create_index(
            "scope",
            name="mood_scope_unique",
            unique=True,
        )

    async def close(self):
        if self.client:
            self.client.close()
            self.client = None

    async def log_event(self, event_type, **data):
        if self.events is None:
            return

        from datetime import datetime, timezone

        await self.events.insert_one(
            {
                "event_type": event_type,
                "data": data,
                "created_at": datetime.now(timezone.utc),
            }
        )


db = Database()
