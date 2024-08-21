import io

from telegram_bot import bot


async def get_user_avatar(telegram_id):
    user_profile_photos = await bot.get_user_profile_photos(telegram_id)
    if user_profile_photos.total_count > 0 and user_profile_photos.photos:
        latest_photo = user_profile_photos.photos[0][0]
        file = await bot.get_file(latest_photo.file_id)
        image_bytes = io.BytesIO()
        await bot.download_file(file_path=file.file_path, destination=image_bytes)
        image_bytes.seek(0)
        return image_bytes.getvalue()
    return None
