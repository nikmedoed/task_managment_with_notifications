import asyncio

from aiogram import Bot
from aiogram.types import Message

from telegram_bot.bot import bot

TIME_TO_DELETE = 60


async def edit_or_resend_message(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup=None):
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup)
    except Exception:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        new_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        return new_message.message_id
    return message_id


async def delete_message_after_delay(chat_id: int, message_id: int):
    await asyncio.sleep(TIME_TO_DELETE)
    await bot.delete_message(chat_id=chat_id, message_id=message_id)


async def send_autodelete_message(text: str, chat_id: int, message: Message = None):
    text = f"{text}\n\n<i>Сообщение автоматически удалится через {TIME_TO_DELETE} секунд</i>."
    if message:
        new_message = await message.answer(text)
    else:
        new_message = await bot.send_message(chat_id, text)
    asyncio.ensure_future(delete_message_after_delay(chat_id, new_message.message_id))
