import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from bot.config.settings import config
from bot.models.database import init_db
from bot.handlers import admin

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()

    token = (getattr(config, "admin_bot_token", None) or "").strip()
    if not token:
        raise RuntimeError("ADMIN_BOT_TOKEN is required")

    timeout = int(getattr(config, "telegram_request_timeout", 7200))
    api_base = (getattr(config, "telegram_api_base", None) or "").strip()
    if api_base:
        api = TelegramAPIServer.from_base(api_base, is_local=bool(getattr(config, "telegram_is_local_api", False)))
        session = AiohttpSession(api=api, timeout=timeout)
    else:
        session = AiohttpSession(timeout=timeout)
    bot = Bot(token=token, session=session)
    dp = Dispatcher()
    dp.include_router(admin.router)
    print("Admin bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

