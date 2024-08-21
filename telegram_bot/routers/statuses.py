import logging

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from database.models import is_valid_transition, SHOULD_BE_COMMENTED, COMPLETED_STATUSES
from shared.app_config import app_config
from shared.db import *
from telegram_bot.utils.keyboards import *
from telegram_bot.utils.message_magic import edit_or_resend_message, send_autodelete_message
from telegram_bot.utils.notifications import send_notify
from telegram_bot.utils.send_tasks import delete_notifications

router = Router()


class CommentStates(StatesGroup):
    waiting_for_comment = State()


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
        notify = await send_notify(task, db, event_msg=f"Обновление задачи", may_edit=True)
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
            await send_autodelete_message(
                f"Статус задачи /{task.id} уже установлен в \"<b>{new_status.value}</b>\".\n"
                f"{inside}",
                chat_id=user.telegram_id,
                message=callback_query.message)
        return

    if not is_valid_transition(task.status, new_status, user_roles):
        await callback_query.answer("Недопустимый перевод статуса для вашей роли", show_alert=True)
        return

    if new_status in SHOULD_BE_COMMENTED:
        await state.update_data(task_id=task.id, status=new_status.name)
        sent_message = await callback_query.message.answer(
            f"Укажите причину установки статуса \"<b>{new_status.value}</b>\" (сообщением), "
            f"или нажмите отмена",
            reply_markup=cancel_keyboard)
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
    await state.update_data(comment=message.text)

    new_message_id = await edit_or_resend_message(
        message.bot,
        chat_id=message.chat.id,
        message_id=user_data.get('message_id'),
        text=f"Причина статуса \"<b>{new_status.value}</b>\":\n"
             f"<pre>{message.text}</pre>\n\n"
             f"Отправить или отменить?\n\n"
             f"Можно прислать новую.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отправить", callback_data="submit_comment")],
                [cancel_button]
            ]
        )
    )
    await state.update_data(message_id=new_message_id)


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
        await send_autodelete_message(
            f"{info}"
            f"<a href='{app_config.domain}/tasks/{task.id}'>Задача</a> в "
            f"<a href='{app_config.domain}/tasks_archive'>архиве</a>.",
            chat_id=user.telegram_id,
            message=callback_query.message)

        notifications = await get_notifications(task.id, user.id, db)
        await delete_notifications(notifications, db)
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
        await delete_notifications(notifications, db)

        await send_autodelete_message(
            f"{info}"
            f"Текущий ответственный: <a href='{user.telegram_bot_link}'>{user_to_notify.full_name}</a>.\n"
            f"Система отправит уведомление и проконтролирует исполнение.",
            chat_id=user.telegram_id,
            message=callback_query.message)

    notify = await send_notify(task, db, event_msg=f"Новая задача в статусе: {new_status.value}\n"
                                                   f"Ваша роль: {task.get_user_roles_text(user_to_notify.id)}",
                               may_edit=True)
    return change
