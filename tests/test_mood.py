import asyncio

from services.mood import MOODS, MOOD_LINES, MoodManager


def test_mood_catalog():
    assert set(MOODS) == {"happy", "sassy", "sulky", "romantic", "sleepy"}
    for mood in MOODS:
        assert MOOD_LINES[mood]


def test_mood_line():
    manager = MoodManager(None)
    for mood in MOODS:
        assert manager.line(mood)


def test_mood_validation():
    async def run():
        class Collection:
            async def update_one(self, *args, **kwargs):
                return None

        class DB:
            db = type("X", (), {"moods": Collection()})()

        manager = MoodManager(DB())
        manager.bind()
        try:
            await manager.set("invalid")
        except ValueError:
            return
        raise AssertionError("invalid mood was accepted")

    asyncio.run(run())
