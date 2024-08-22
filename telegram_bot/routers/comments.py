import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, TaskNotification
from shared.db import add_comment, get_task_by_id, add_error
from telegram_bot.utils.keyboards import generate_status_keyboard
from telegram_bot.utils.send_tasks import get_telegram_task_text, send_task_message

router = Router()


@router.message(F.reply_to_message)
async def handle_reply(message: Message, user: User, db: AsyncSession):
    if not message.reply_to_message:
        await message.reply(
            "Для комментирования нужно использовать функцию 'ответить' на сообщение (reply). "
            "Это нужно, чтобы понять, какую задачу вы комментируете.\n\n"
            "Чтобы 'ответить' смахните сообщение влево, коснитесь сообщения и выберите в меню, "
            "или через правую кнопку мыши на компьютере.")
        return

    telegram_id = message.from_user.id
    reply_message_id = message.reply_to_message.message_id

    notification: TaskNotification = (await db.execute(select(TaskNotification).filter_by(
        telegram_message_id=reply_message_id,
        user_id=user.id,
        active=True
    ))).scalar_one_or_none()

    if not notification:
        await message.reply(
            "Комментировать можно только задачи. Не получилось найти задачу, связанную с сообщением")
        return

    task = await get_task_by_id(notification.task_id, db)
    if not task:
        await message.answer("Задача более недоступна в базе")
        return

    await add_comment(task, user, message.text, db)
    await db.refresh(task)

    task_info = get_telegram_task_text(task, "Новый комментарий по задаче")

    users = {task.supplier, task.supervisor, task.executor}
    for user in users:
        try:
            is_initiator = user.telegram_id == telegram_id
            await send_task_message(task_info, task, user, user_message=message if is_initiator else None, db=db,
                                    markup=generate_status_keyboard(user, task), may_edit=not is_initiator)
        except TelegramAPIError as e:
            logging.error(f"Failed to send message to {user.telegram_id} for task {task.id}: {e}")
            await add_error(task.id, f"Ошибка отправки уведомления:\n{e}", user.id, db)
    await message.delete()
