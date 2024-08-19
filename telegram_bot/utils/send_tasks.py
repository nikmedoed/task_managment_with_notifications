import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_sessionmaker import get_db
from database.models import Task, User, CommentType, Statuses
from shared.app_config import app_config
from shared.db import add_error, add_notification, get_notifications


def get_telegram_task_text(task: Task, event: str = "") -> str:
    task_info = (
        f"<b>№ п/п:</b> /{task.id}{' ❗️<b>важная</b>' if task.important else ''}\n"
        f"<b>Создано:</b> {task.time_created.strftime('%d.%m.%Y')}\n"
        f"<b>Обновлено:</b> {task.time_updated.strftime('%d.%m.%Y')}\n"
        f"<b>Объект:</b> {task.object.name}\n"
        f"<b>Тип:</b> <a href='{app_config.domain}/tasks/{task.id}'>{task.task_type.name}</a>\n"
        f"<b>Срок:</b> {task.formatted_plan_date}\n"
        f"<b>Статус:</b> {task.status.value}\n"
        f"<b>Описание:</b>\n {task.description}\n"
        f"\n"
        f"<b>Постановщик:</b> <a href='{task.supplier.telegram_bot_link}'>{task.supplier.full_name}</a>\n"
        f"<b>Руководитель:</b> <a href='{task.supervisor.telegram_bot_link}'>{task.supervisor.full_name}</a>\n"
        f"<b>Исполнитель:</b> <a href='{task.executor.telegram_bot_link}'>{task.executor.full_name}</a>\n"
    )

    if event:
        task_info = f"<b>{event}</b>\n\n{task_info}"

    if task.comments:
        comments = []
        has_comment = False

        for comment in reversed(task.comments):
            has_comment = has_comment or comment.type == CommentType.comment
            comments.append(format_comment(comment))
            if len(comments) >= 5 and has_comment:
                break
        comments.reverse()
        task_info = f"{task_info}\n\n<b>Последние комментарии</b>\n\n{'\n\n'.join(comments)}"

    return task_info


def format_comment(comment):
    roles = ', '.join([role[0] for role in comment.author_roles])
    comment_info = [f"<b>{comment.time_updated.strftime('%d.%m.%y %H:%M')}</b>"]
    if comment.user:
        comment_info.append(f"<b>{comment.user.short_name}</b>")
    if roles:
        comment_info.append(f"({roles})")
    comment_info = " ".join(comment_info)

    if comment.type == CommentType.status_change:
        comment_info += (
            f"\n🔁 Статус \"{Statuses[comment.previous_status].value}\" → "
            f"\"{Statuses[comment.new_status].value}\""
        )
    elif comment.type == CommentType.date_change:
        diff_days = (comment.new_date - comment.old_date).days
        comment_info += (
            f"\n🗓 Срок до \"{comment.old_date.strftime('%d.%m.%Y')}\" → "
            f"\"{comment.new_date.strftime('%d.%m.%Y')}\" "
            f"({f'+{diff_days}' if diff_days > 0 else diff_days} дн.)"
        )
    elif comment.type == CommentType.user_change:
        comment_info += (
            f"\n💁‍♂️ {'Исполнитель' if comment.extra_data['role'] == 'executor' else 'Руководитель'} "
            f"\"{comment.extra_data['old_user']['name']}\" → "
            f"\"{comment.extra_data['new_user']['name']}\""
        )
    if comment.content:
        if comment.type == CommentType.error:
            comment_info += f"\n⚠️ <i>{comment.content.strip()}</i>"
        else:
            comment_info += (f"\n{'💬 ' if comment.type == CommentType.comment else ''}"
                             f"{comment.content.strip()}")

    if comment.documents:
        documents_info = "\n".join(
            f"- {doc.title}" if doc.deleted else f"- <a href='{app_config.domain}/documents/{doc.uuid}'>{doc.title}</a>"
            for doc in comment.documents
        )
        comment_info += f"\n{documents_info}"

    return comment_info


async def send_task_message(text: str, task: Task, user: User,
                            user_message: Message = None,
                            db: AsyncSession = None,
                            markup: InlineKeyboardMarkup = None,
                            bot: Bot = None,
                            may_edit: bool = False) -> Message | None:
    if db is None:
        db = await anext(get_db())
    if not bot:
        from telegram_bot.bot import bot

    notifications = await get_notifications(task.id, user.id, db)
    new_message = None

    if notifications and may_edit:
        latest_notification = notifications[-1]
        try:
            edit_success = False
            if text:
                try:
                    new_message = await bot.edit_message_text(
                        chat_id=latest_notification.user.telegram_id,
                        message_id=latest_notification.telegram_message_id,
                        text=text
                    )
                    edit_success = True
                except TelegramAPIError as e:
                    if "message content and reply markup are exactly" not in str(e):
                        raise e
            if markup:
                try:
                    new_message = await bot.edit_message_reply_markup(
                        chat_id=latest_notification.user.telegram_id,
                        message_id=latest_notification.telegram_message_id,
                        reply_markup=markup
                    )
                    edit_success = True
                except TelegramAPIError as e:
                    if "message content and reply markup are exactly" not in str(e):
                        raise e
            if edit_success:
                notifications = notifications[:-1]
        except TelegramAPIError as e:
            logging.error(f"Failed to edit message {latest_notification.telegram_message_id}: {e}")

    # Удаление всех оставшихся уведомлений (если редактирование не удалось или его не было)
    for notification in notifications:
        try:
            await bot.delete_message(notification.user.telegram_id, notification.telegram_message_id)
            notification.active = False
            await db.commit()
        except TelegramAPIError as e:
            err = str(e)
            if 'message to delete not found' in err:
                notification.active = False
                await db.commit()
            else:
                logging.error(f"Failed to delete message {notification.telegram_message_id}: {err}")
                await add_error(task.id, notification.user_id, f"Ошибка удаления устаревшего уведомления:\n{err}", db)

    # Если редактирование не удалось или уведомлений не было, отправляем новое сообщение
    if not new_message:
        try:
            if user_message:
                new_message = await user_message.answer(
                    text,
                    reply_markup=markup
                )
            else:
                new_message = await bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=markup
                )
            await add_notification(task, user.id, new_message.message_id, db)
        except TelegramAPIError as e:
            logging.error(f"Failed to send message to {user.telegram_id} for task {task.id}: {e}")
            await add_error(task.id, user.id, f"Ошибка отправки уведомления:\n{e}", db)

    return new_message
