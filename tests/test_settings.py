import os


def test_project_imports(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "ci-test-token")
    monkeypatch.setenv("API_ID", "12345")
    monkeypatch.setenv("API_HASH", "ci-test-api-hash")
    monkeypatch.setenv(
        "MONGO_URI",
        "mongodb://localhost:27017/telegram_userbot_test",
    )
    monkeypatch.setenv(
        "SESSION_ENCRYPTION_KEY",
        "gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    monkeypatch.setenv("ADMIN_IDS", "123456789")

    import config
    import database
    import services.task_manager
    import utils.security

    assert config.settings.api_id == 12345
