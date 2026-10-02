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

        self.db = self.client[
            settings.database_name
        ]

        self.users = self.db.users
        self.tasks = self.db.tasks
        self.events = self.db.events
        self.moods = self.db.moods

        # ====================================================
        # USERS INDEX CLEANUP
        # ====================================================
        #
        # Old versions of the project may have created:
        #
        #   user_id_1
        #   bot_user_id_1
        #   telegram_user_id_1
        #
        # Some of those indexes are unique and can fail when
        # older documents contain null values.
        #
        # Remove only indexes by their actual indexed field.
        # ====================================================

        indexes = await self.users.list_indexes().to_list(
            length=None
        )

        for index in indexes:
            index_name = index.get("name")
            key = index.get("key")

            # ------------------------------------------------
            # Remove obsolete user_id indexes.
            # ------------------------------------------------

            if key == {"user_id": 1}:
                await self.users.drop_index(
                    index_name
                )

            # ------------------------------------------------
            # Remove old bot_user_id indexes.
            # They will be recreated correctly below.
            # ------------------------------------------------

            elif key == {"bot_user_id": 1}:
                await self.users.drop_index(
                    index_name
                )

            # ------------------------------------------------
            # Remove old telegram_user_id indexes.
            # They will be recreated as sparse below.
            # ------------------------------------------------

            elif key == {"telegram_user_id": 1}:
                await self.users.drop_index(
                    index_name
                )

        # ====================================================
        # CORRECT BOT USER INDEX
        # ====================================================
        #
        # bot_user_id is the Telegram ID of the person using
        # the CONTROL BOT.
        #
        # Only positive IDs are indexed.
        #
        # Therefore null/missing legacy documents do not
        # collide with the unique index.
        # ====================================================

        await self.users.create_index(
            "bot_user_id",
            name="bot_user_id_unique",
            unique=True,
            partialFilterExpression={
                "bot_user_id": {
                    "$gt": 0
                }
            },
        )

        # ====================================================
        # TELEGRAM ACCOUNT INDEX
        # ====================================================
        #
        # Multiple legacy records may not have this field.
        # Sparse prevents null/missing values from creating
        # an unwanted uniqueness conflict.
        # ====================================================

        await self.users.create_index(
            "telegram_user_id",
            name="telegram_user_id_sparse",
            sparse=True,
        )

        # ====================================================
        # TASK INDEXES
        # ====================================================

        await self.tasks.create_index(
            [
                ("bot_user_id", 1),
                ("created_at", -1),
            ],
            name="bot_user_id_created_at",
        )

        await self.tasks.create_index(
            [
                ("status", 1),
                ("created_at", -1),
            ],
            name="status_created_at",
        )

        # ====================================================
        # EVENT INDEX
        # ====================================================

        await self.events.create_index(
            [
                ("created_at", -1),
            ],
            name="events_created_at",
        )

        # ====================================================
        # MOOD INDEX
        # ====================================================

        await self.moods.create_index(
            "scope",
            name="mood_scope_unique",
            unique=True,
        )

    async def close(self):
        if self.client:
            self.client.close()

    async def log_event(
        self,
        name,
        bot_user_id=None,
        **fields,
    ):
        from utils.helpers import utcnow

        document = {
            "name": name,
            "bot_user_id": bot_user_id,
            "fields": fields,
            "created_at": utcnow(),
        }

        await self.events.insert_one(
            document
        )


db = Database()
