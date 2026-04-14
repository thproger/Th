import asyncio
import logging
from aiohttp import web
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import db
from handlers import register_all_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def keep_alive(url):
    # Використовуємо одну сесію для ефективності
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    # Можна розкоментувати для відладки:
                    # print(f"Ping success: {response.status}")
                    pass
            except Exception as e:
                print(f"Ping error: {e}")
            
            # Чекаємо 50 секунд перед наступним запитом
            await asyncio.sleep(50)

async def health_check(request):
    return web.Response(text="Bot is alive!")

async def main():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Фейковий сервер запущено на порту {port}")
    url = "https://th-nph3.onrender.com"
    asyncio.create_task(keep_alive(url))
    
    print("Бот запущений, анти-сон активовано!")

    await db.connect()
    await db.create_indexes()
    logger.info("Connected to MongoDB")

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    register_all_handlers(dp)

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
