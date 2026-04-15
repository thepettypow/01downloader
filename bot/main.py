import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot.config.settings import config
from bot.models.database import init_db
from bot.handlers import start, download, admin

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(download.router)
    
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
