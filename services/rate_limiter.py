import asyncio
import time


class RateLimiter:
    def __init__(self):
        self.last_sent = {}

    async def wait(self, key: str, delay: float):
        now = time.monotonic()
        last = self.last_sent.get(key)
        if last is not None:
            remaining = delay - (now - last)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self.last_sent[key] = time.monotonic()
