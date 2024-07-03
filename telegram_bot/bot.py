from aiogram import Bot, Dispatcher
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from shared.app_config import TELEGRAM_TOKEN
from telegram_bot.handlers import user, task

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

dp.middleware.setup(LoggingMiddleware())

# Register handlers
user.register_handlers(dp)
task.register_handlers(dp)

async def start_bot():
    await dp.start_polling()
