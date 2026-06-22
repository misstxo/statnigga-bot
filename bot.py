import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import db
from handlers import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]          # e.g. https://your-app.onrender.com
WEBHOOK_PATH = "/webhook"
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 10000))


async def on_startup(bot: Bot):
    await db.init_db()
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info("Webhook set to %s%s", WEBHOOK_URL, WEBHOOK_PATH)


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()


def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
