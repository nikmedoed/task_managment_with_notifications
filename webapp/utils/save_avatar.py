import os
from pathlib import Path

import aiofiles

from database.models import User
from telegram_bot.utils.get_user_photo import get_user_avatar

AVATAR_DIR = Path("avatars")

os.makedirs(AVATAR_DIR, exist_ok=True)


async def save_avatar_to_disk(user: User):
    avatar_data = await get_user_avatar(user.telegram_id)
    if avatar_data:
        avatar_path = AVATAR_DIR / f"{user.id}.jpg"
        async with aiofiles.open(avatar_path, 'wb') as out_file:
            await out_file.write(avatar_data)
