import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import cast, Date, and_, select
from sqlalchemy.orm import joinedload

from database import async_dbsession
from database.models import (Task, COMPLETED_STATUSES, Comment, SUPPLIER_STATUSES,
                             SUPERVISOR_STATUSES, EXECUTOR_STATUSES)
from telegram_bot.utils.send_tasks import get_telegram_task_text, send_task_message


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

            text = get_telegram_task_text(task, event_msg)
            markup = None
            await send_task_message(text, task, user_to_notify, db=db, markup=markup, bot=bot, may_edit=False)
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(notify_user_tasks())
