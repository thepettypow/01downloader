import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from bot.config.settings import config
from bot.models.database import init_db
from bot.handlers import start, download, admin
from bot.utils.cleanup import cleanup_downloads

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    timeout = int(getattr(config, "telegram_request_timeout", 7200))
    api_base = (getattr(config, "telegram_api_base", None) or "").strip()
    if api_base:
        api = TelegramAPIServer.from_base(api_base, is_local=bool(getattr(config, "telegram_is_local_api", False)))
        session = AiohttpSession(api=api, timeout=timeout)
    else:
        session = AiohttpSession(timeout=timeout)
    bot = Bot(token=config.bot_token, session=session)
    dp = Dispatcher()
    
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(download.router)
    
    async def cleanup_loop():
        while True:
            try:
                retention_h = int(getattr(config, "download_retention_hours", 12))
                max_age = max(0, retention_h) * 3600
                cleanup_downloads(config.download_dir, max_age)
            except Exception:
                pass
            await asyncio.sleep(int(getattr(config, "cleanup_interval_seconds", 3600)))

    asyncio.create_task(cleanup_loop())
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
