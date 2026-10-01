from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def human_seconds(seconds: int) -> str:
    minutes, sec = divmod(max(0, int(seconds)), 60)
    return f"{minutes}m {sec}s" if minutes else f"{sec}s"
