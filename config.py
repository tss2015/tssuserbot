import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    mongo_uri: str
    session_encryption_key: str
    admin_ids: tuple[int, ...]
    tag_delay: float
    tag_batch_size: int
    max_members_per_task: int
    log_level: str
    database_name: str
    auth_timeout: int
    health_port: int
    maintenance: bool
    enable_scheduled_messages: bool
    groq_api_key: str
    groq_model: str
    groq_timeout: int

    @classmethod
    def from_env(cls):
        return cls(
            bot_token=required("BOT_TOKEN"),
            api_id=int(required("API_ID")),
            api_hash=required("API_HASH"),
            mongo_uri=required("MONGO_URI"),
            session_encryption_key=required("SESSION_ENCRYPTION_KEY"),
            admin_ids=csv_ints(os.getenv("ADMIN_IDS", "")),
            tag_delay=max(1.0, float(os.getenv("TAG_DELAY", "5"))),
            tag_batch_size=max(1, min(10, int(os.getenv("TAG_BATCH_SIZE", "5")))),
            max_members_per_task=max(1, int(os.getenv("MAX_MEMBERS_PER_TASK", "5000"))),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_name=os.getenv("DATABASE_NAME", "telegram_userbot"),
            auth_timeout=max(60, int(os.getenv("AUTH_TIMEOUT", "300"))),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
            maintenance=os.getenv("MAINTENANCE", "false").lower() == "true",
            enable_scheduled_messages=os.getenv("ENABLE_SCHEDULED_MESSAGES", "false").lower() == "true",
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            groq_timeout=max(5, int(os.getenv("GROQ_TIMEOUT", "20"))),
        )


settings = Settings.from_env()
