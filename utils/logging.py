import logging

logger = logging.getLogger("userbot")

def event(name: str, **fields):
    safe = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("%s | %s", name, safe)
