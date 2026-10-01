import asyncio
from aiohttp import web

from config import settings
from database import db
from services.task_manager import task_manager

_started = False


async def health(request):
    return web.json_response({
        "status": "ok",
        "database": bool(db.db),
        "active_tasks": task_manager.active_count(),
    })


async def start_health_server():
    global _started
    if _started:
        return
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.health_port)
    await site.start()
    _started = True
