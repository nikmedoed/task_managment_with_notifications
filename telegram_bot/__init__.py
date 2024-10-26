import asyncio
import importlib
import logging
import pkgutil
from pathlib import Path

import aiocron
from aiogram import Dispatcher, Bot, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from shared.app_config import app_config
from telegram_bot.bot import bot
from telegram_bot.middlewares import UserAndDBSessionCheckMiddleware
from telegram_bot.utils.notifications import notify_everyday_tasks_deadlines, send_notify

logging.basicConfig(level=logging.getLevelName(app_config.log_level.upper()))
logger = logging.getLogger(__name__)


async def register_routers(dp: Dispatcher, bot: Bot):
    commands = {}
    routers_path = Path(__file__).parent / 'routers'
    for _, module_name, _ in pkgutil.iter_modules([str(routers_path)]):
        full_module_name = f"telegram_bot.routers.{module_name}"
        try:
            imported_module = importlib.import_module(full_module_name)
            if hasattr(imported_module, 'router'):
                dp.include_router(imported_module.router)
                logger.info(f"Router from module '{full_module_name}' successfully included.")

                if hasattr(imported_module, 'commands'):
                    commands.update(imported_module.commands)
            else:
                logger.warning(f"Module '{full_module_name}' does not have a 'router' attribute.")
        except Exception as e:
            logger.error(f"Failed to import module '{full_module_name}': {e}")
    await bot.set_my_commands([BotCommand(command=f"/{c}", description=d) for c, d in commands.items()])


async def start_bot():
    storage = RedisStorage.from_url(app_config.redis.url)
    dp = Dispatcher(storage=storage)

    dp.update.middleware(UserAndDBSessionCheckMiddleware())
    await register_routers(dp, bot)

    @dp.error()
    async def error_handler(event: types.error_event.ErrorEvent):
        logger.error(f"Update: {event.update} \n{event.exception}", exc_info=True)
        return True

    cron_job = aiocron.crontab('0 9 * * *', func=notify_everyday_tasks_deadlines, start=True)

    await dp.start_polling(bot, skip_updates=False)


if __name__ == "__main__":
    asyncio.run(start_bot())
