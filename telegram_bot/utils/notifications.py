import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot
from sqlalchemy import cast, Date, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import async_dbsession, get_db
from database.models import (Task, NOTIFICATION_STATUSES, Comment)
from shared.db import get_notifications
from telegram_bot.utils.keyboards import generate_status_keyboard
from telegram_bot.utils.send_tasks import get_telegram_task_text, send_task_message, delete_notifications


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


async def notify_everyday_tasks_deadlines(bot: Bot = None):
    if not bot:
        from telegram_bot.bot import bot

    now = date.today()
    date_ranges = [(now + timedelta(days=x)) for x in WHEN_REMEMBER]

    tasks_query = select(Task).options(
        joinedload(Task.comments).joinedload(Comment.user),
        joinedload(Task.comments).joinedload(Comment.documents)
    ).filter(
        and_(
            cast(Task.actual_plan_date, Date).in_(date_ranges),
            Task.status.in_(NOTIFICATION_STATUSES)
        )
    ).order_by(Task.actual_plan_date)

    async with async_dbsession() as db:
        tasks = (await db.execute(tasks_query)).scalars().unique().all()

        for task in tasks:
            days_remain = (task.actual_plan_date - now).days
            event_msg = (f"Напоминание о задаче со сроком через "
                         f"{days_remain} {DAYS_WORD.get(days_remain, 'дней')}")

            await send_notify(task, db, bot, event_msg=event_msg, may_edit=False)
            await asyncio.sleep(0.1)


async def send_notify(task: Task, db: AsyncSession, bot: Bot, event_msg: str = "", may_edit=False):
    user_to_notify = task.whom_notify()
    if not user_to_notify:
        logging.warning(f"No relevant user to notify about {task} - {task.description}")
        notifications = await get_notifications(task.id, db=db)
        await delete_notifications(notifications, bot, db)
        return

    text = get_telegram_task_text(task, event_msg)
    markup = generate_status_keyboard(user_to_notify, task)

    return await send_task_message(text, task, user_to_notify, db=db, markup=markup, bot=bot, may_edit=may_edit)


# async def notify_event(task: Task, db: AsyncSession = None, bot: Bot = None):
#     if task.status not in NOTIFICATION_STATUSES:
#         return
#     if not bot:
#         from telegram_bot.bot import bot
#     if db is None:
#         db = await anext(get_db())
#     await send_notify(task, db, bot, event_msg="Новый статус???", may_edit=True)


if __name__ == "__main__":
    asyncio.run(notify_everyday_tasks_deadlines())
