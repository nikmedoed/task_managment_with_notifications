import io
import logging

from aiogram.exceptions import TelegramAPIError

from telegram_bot import bot


async def get_user_avatar(telegram_id: int):
    try:
        user_profile_photos = await bot.get_user_profile_photos(telegram_id)
        if not user_profile_photos.total_count:
            return None

        file = await bot.get_file(user_profile_photos.photos[0][0].file_id)
        image_bytes = io.BytesIO()
        await bot.download_file(file_path=file.file_path, destination=image_bytes)
        image_bytes.seek(0)
        return image_bytes.getvalue()
    except TelegramAPIError as e:
        logging.error(f"Error while fetching user avatar: {e}")
    return None
