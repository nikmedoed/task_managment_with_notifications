import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, TaskNotification, Task
from shared.db import add_comment, get_task_by_id, add_error
from telegram_bot.utils.send_tasks import get_telegram_task_text, send_task_message

router = Router()


class AcknowledgeCallback(CallbackData, prefix="ack"):
    task_id: int


@router.message(F.reply_to_message)
async def handle_reply(message: Message, user: User, db: AsyncSession):
    bot = message.bot
    if not message.reply_to_message:
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
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(
            text="Ознакомлен, скрыть",
            callback_data=AcknowledgeCallback(task_id=task.id).pack()
        )
    )
    markup = keyboard.as_markup()

    users = {task.supplier, task.supervisor, task.executor}
    for user in users:
        try:
            if user.telegram_id != telegram_id:
                await send_task_message(task_info, task, user,
                                        db=db, markup=markup, bot=bot, may_edit=True)
            else:
                await send_task_message(task_info, task, user,
                                        db=db, user_message=message, bot=bot,
                                        markup=None, may_edit=False)
                await message.delete()
        except TelegramAPIError as e:
            logging.error(f"Failed to send message to {user.telegram_id} for task {task.id}: {e}")
            await add_error(task.id, user.id, f"Ошибка отправки уведомления:\n{e}", db)


@router.callback_query(AcknowledgeCallback.filter())
async def handle_acknowledge(call: CallbackQuery, callback_data: AcknowledgeCallback,
                             user: User, db: AsyncSession):
    task = await db.get(Task, callback_data.task_id)
    if not task:
        await call.answer("Задача более недоступна в базе")
        return
    await add_comment(task, user, "Ознакомился с комментарием в телеграм", db)
    await call.message.delete()
    await call.answer("Записано")
