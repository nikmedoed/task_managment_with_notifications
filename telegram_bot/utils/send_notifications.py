import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import cast, Date, and_
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database import async_dbsession
from database.models import (Task, COMPLETED_STATUSES, TaskNotification, Comment, CommentType,
                             SUPPLIER_STATUSES, SUPERVISOR_STATUSES, EXECUTOR_STATUSES)
from telegram_bot.utils.send_tasks import send_task


def get_days_text(days_remain):
    if 11 <= days_remain % 100 <= 14:
        return "дней"
    elif days_remain % 10 == 1:
        return "день"
    elif 2 <= days_remain % 10 <= 4:
        return "дня"
    else:
        return "дней"


WHEN_REMEMBER = [0, 1, 3, 7]
DAYS_WORD = {d: get_days_text(d) for d in [0, 1, 3, 7]}


async def notify_user_tasks(bot: Bot = None):
    if not bot:
        from telegram_bot.bot import bot

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_ranges = [(now + timedelta(days=x)).date() for x in WHEN_REMEMBER]

    tasks_query = select(Task).options(
        joinedload(Task.comments).joinedload(Comment.user),
        joinedload(Task.comments).joinedload(Comment.documents)
    ).filter(
        and_(
            cast(Task.actual_plan_date, Date).in_(date_ranges),
            Task.status.notin_(COMPLETED_STATUSES)
        )
    ).order_by(Task.actual_plan_date)

    async with async_dbsession() as db:
        tasks = (await db.execute(tasks_query)).scalars().unique().all()

        async def save_error(tid, uid, err):
            erc = Comment(type=CommentType.error, task_id=tid, user_id=uid, content=err)
            db.add(erc)
            await db.commit()

        for task in tasks:
            days_remain = (task.actual_plan_date - now).days
            event_msg = (f"Напоминание о задаче со сроком через "
                         f"{days_remain} {DAYS_WORD.get(days_remain, 'дней')}")

            if task.status in SUPPLIER_STATUSES:
                user_to_notify = task.supplier
            elif task.status in SUPERVISOR_STATUSES:
                user_to_notify = task.supervisor
            elif task.status in EXECUTOR_STATUSES:
                user_to_notify = task.executor
            else:
                logging.warning(f"No relevant user to notify about {task} from {days_remain} - {task.description}")
                continue

            try:
                message = await send_task(task, user_to_notify, event=event_msg)
            except TelegramAPIError as e:
                logging.error(f"Failed to send message to {user_to_notify.telegram_id} for task {task.id}: {e}")
                await save_error(task.id, user_to_notify.id,
                                 f"Ошибка отправки уведомления:\n{e}")
                continue

            notifications = (await db.execute(
                select(TaskNotification).filter_by(task_id=task.id, active=True)
            )).scalars().all()

            new_notification = TaskNotification(
                task_id=task.id,
                user_id=user_to_notify.id,
                telegram_message_id=message.message_id,
                active=True
            )
            db.add(new_notification)
            task.notification_count += 1
            await db.commit()

            for notification in notifications:
                try:
                    await bot.delete_message(notification.user.telegram_id, notification.telegram_message_id)
                    notification.active = False
                except TelegramAPIError as e:
                    err = str(e)
                    if 'message to delete not found' in err:
                        notification.active = False
                    else:
                        logging.error(
                            f"Failed to delete message {notification.telegram_message_id} "
                            f"for user {notification.user.telegram_id}: {err}")
                        await save_error(task.id, user_to_notify.id,
                                         f"Ошибка удаления устаревшего уведомления:\n{err}")
                        continue

            await db.commit()
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(notify_user_tasks())
