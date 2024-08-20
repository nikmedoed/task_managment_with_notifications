import asyncio
import logging

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Task, Statuses, User, is_valid_transition, SHOULD_BE_COMMENTED, COMPLETED_STATUSES
from shared.app_config import app_config
from shared.db import add_comment, status_change, get_task_by_id, get_notifications, add_error
from telegram_bot.utils.keyboards import StatusChangeCallback, AcknowledgeCallback
from telegram_bot.utils.notifications import send_notify
from telegram_bot.utils.send_tasks import delete_notifications

router = Router()


class CommentStates(StatesGroup):
    waiting_for_comment = State()


TIME_TO_DELETE = 60


async def delete_message_after_delay(bot: Bot, chat_id: int, message_id: int):
    await asyncio.sleep(TIME_TO_DELETE)
    await bot.delete_message(chat_id=chat_id, message_id=message_id)


async def run_status_change(task: Task, user: User, new_status: Statuses, db: AsyncSession,
                            bot: Bot, callback_query: CallbackQuery, comment=None):
    previous_status = task.status.value
    change = await status_change(task, user, new_status, comment, db=db)
    if not change:
        await callback_query.answer("Проблема при смене статуса")
        return
    await callback_query.answer(f"Статус изменен на {new_status.value}")

    user_to_notify = task.whom_notify()

    info = (f"Статус задачи /{task.id} успешно изменён\n"
            f"\"<b>{previous_status}</b>\" → \"<b>{new_status.value}</b>\".\n\n")
    if new_status in COMPLETED_STATUSES:
        message = await callback_query.message.answer(
            f"{info}"
            f"<a href='{app_config.domain}/tasks/{task.id}'>Задача</a> в "
            f"<a href='{app_config.domain}/tasks_archive'>архиве</a>."
            f"\n\n<i>Сообщение автоматически удалится через {TIME_TO_DELETE} секунд</i>."
        )
        asyncio.ensure_future(delete_message_after_delay(bot, user.telegram_id, message.message_id))
        notifications = await get_notifications(task.id, user.id, db)
        await delete_notifications(notifications, bot, db)
        return

    if not user_to_notify:
        await add_error(task.id, f"Не получилось определить ответственного за статус {new_status.value}", user.id)
        message = await callback_query.message.answer(
            f"{info}"
            f"⚠️ Cтатус не считается конечным, но ответственного за статус не получилось определить.\n"
            f"Пожалуйста перейдите в <a href='{app_config.domain}/tasks/{task.id}'>карточку задачи на сайте</a> "
            f"и проверьте назначенных пользователей."
        )
        return

    logging.info(f"{previous_status} -> {new_status.value} "
                 f"notify {user_to_notify.id}::{user_to_notify.full_name} "
                 f"actor {user.id}::{user.full_name}")

    if user_to_notify.id != user.id:
        notifications = await get_notifications(task.id, user.id, db)
        await delete_notifications(notifications, bot, db)

        message = await callback_query.message.answer(
            f"{info}"
            f"Текущий ответственный: <a href='{user.telegram_bot_link}'>{user_to_notify.full_name}</a>.\n"
            f"Система отправит уведомление и проконтролирует исполнение."
            f"\n\n<i>Сообщение автоматически удалится через {TIME_TO_DELETE} секунд</i>."
        )
        asyncio.ensure_future(delete_message_after_delay(bot, user.telegram_id, message.message_id))

    notify = await send_notify(task, db, bot,
                               event_msg=f"Новая задача в статусе: {new_status.value}\n"
                                         f"Ваша роль: {task.get_user_roles_text(user_to_notify.id)}",
                               may_edit=True)
    return change


@router.callback_query(StatusChangeCallback.filter())
async def handle_status_change(callback_query: CallbackQuery,
                               callback_data: StatusChangeCallback, state: FSMContext,
                               user: User, db: AsyncSession, bot: Bot):
    task = await get_task_by_id(callback_data.task_id, db)
    if not task:
        await callback_query.answer("Задача не найдена", show_alert=True)
        return

    new_status = Statuses[callback_data.status]
    user_roles = task.get_user_roles(user.id)

    if new_status == task.status:
        notify = await send_notify(task, db, bot, event_msg=f"Обновление задачи", may_edit=True)
        await callback_query.answer("Обновили описание")
        if not notify:
            if new_status in COMPLETED_STATUSES:
                inside = "Это конечный статус, поэтому описание задачи удалено."
            else:
                inside = (f"⚠️ Cтатус не считается конечным, но ответственного за статус не получилось определить.\n"
                          f"Пожалуйста перейдите в <a href='{app_config.domain}/tasks/{task.id}'>карточку задачи на сайте</a> "
                          f"и проверьте назначенных пользователей.")
                await add_error(task.id,
                                f"Не получилось определить ответственного за статус {new_status.value}",
                                user.id)
            message = await callback_query.message.answer(
                f"Статус задачи /{task.id} уже установлен в \"<b>{new_status.value}</b>\".\n"
                f"{inside}"
                f"\n\n<i>Сообщение автоматически удалится через {TIME_TO_DELETE} секунд</i>."
            )
            if new_status in COMPLETED_STATUSES:
                asyncio.ensure_future(delete_message_after_delay(bot, user.telegram_id, message.message_id))
        return

    if not is_valid_transition(task.status, new_status, user_roles):
        await callback_query.answer("Недопустимый перевод статуса для вашей роли", show_alert=True)
        return

    if new_status in SHOULD_BE_COMMENTED:
        await state.update_data(task_id=task.id, status=new_status.name)
        sent_message = await callback_query.message.answer(
            f"Укажите причину установки статуса \"<b>{new_status.value}</b>\" (сообщением), "
            f"или нажмите отмена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
                ]
            ))
        await state.update_data(message_id=sent_message.message_id)
        await state.set_state(CommentStates.waiting_for_comment)
        await callback_query.answer("Обоснуйте")
    else:
        await run_status_change(task, user, new_status, db, bot, callback_query,
                                comment="Изменено из бота")


@router.message(CommentStates.waiting_for_comment)
async def receive_comment(message: Message, state: FSMContext):
    await message.delete()
    user_data = await state.get_data()

    new_status = Statuses[user_data['status']]
    message_id = user_data.get('message_id')
    await state.update_data(comment=message.text)

    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message_id,
        text=f"Причина статуса \"<b>{new_status.value}</b>\":\n"
             f"<pre>{message.text}</pre>\n\n"
             f"Отправить или отменить?\n\n"
             f"Можно прислать новую.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отправить", callback_data="submit_comment")],
                [InlineKeyboardButton(text="Отменить", callback_data="cancel")]
            ]
        ))


@router.callback_query(F.data == "submit_comment", CommentStates.waiting_for_comment)
async def submit_comment(callback_query: CallbackQuery, state: FSMContext, db: AsyncSession, user: User):
    user_data = await state.get_data()
    bot = callback_query.bot
    task_id = user_data['task_id']
    comment = user_data['comment']
    new_status = Statuses[user_data['status']]

    task = await get_task_by_id(task_id, db)
    if not task:
        await callback_query.answer("Задача не найдена", show_alert=True)
        await state.clear()
        return

    if await run_status_change(task, user, new_status, db, bot, callback_query, comment):
        await callback_query.message.delete()
        await state.clear()


@router.callback_query(F.data == "cancel", CommentStates.waiting_for_comment)
async def cancel_comment(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await callback_query.answer("Действие отменено")
    await state.clear()


@router.callback_query(AcknowledgeCallback.filter())
async def handle_acknowledge(call: CallbackQuery, callback_data: AcknowledgeCallback, user: User, db: AsyncSession):
    task = await db.get(Task, callback_data.task_id)
    if not task:
        await call.answer("Задача более недоступна в базе")
        return
    await add_comment(task, user, "Ознакомился с описанием и комментариями в телеграм", db)  # noqa
    await call.message.delete()
    await call.answer("Записано")
