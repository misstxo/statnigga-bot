import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher

import db
from handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))


async def health(request):
    return web.Response(text="ok")


async def run_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await db.init_db()
    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=["message"])


async def run_web():
    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Health server on port %d", PORT)


async def main():
    await asyncio.gather(run_web(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
