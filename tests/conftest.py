import os

os.environ["BOT_TOKEN"] = "ci-test-token"
os.environ["API_ID"] = "12345"
os.environ["API_HASH"] = "ci-test-api-hash"
os.environ["MONGO_URI"] = "mongodb://localhost:27017/telegram_userbot_test"
os.environ["SESSION_ENCRYPTION_KEY"] = (
    "gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)
os.environ["ADMIN_IDS"] = "123456789"
os.environ["TAG_BATCH_SIZE"] = "1"
