from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from shared.app_config import app_config

bot = Bot(token=app_config.telegram.token,
          default=DefaultBotProperties(
              parse_mode=ParseMode.HTML,
              link_preview_is_disabled=True
          ))
