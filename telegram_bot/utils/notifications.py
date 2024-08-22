import asyncio
import logging
from datetime import date, timedelta
from functools import lru_cache

from sqlalchemy import and_, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import async_dbsession, get_db_safety
from database.models import Task, NOTIFICATION_STATUSES, Comment, User, UserRole
from shared.db import get_notifications, notify_sent, get_notified_users
from telegram_bot.utils.keyboards import generate_status_keyboard
from telegram_bot.utils.send_tasks import get_telegram_task_text, send_task_message, delete_notifications, check_task


@lru_cache(maxsize=None)
def get_days_text(days_remain):
    if 11 <= days_remain % 100 <= 14:
        return "дней"
    elif days_remain % 10 == 1:
        return "день"
    elif 2 <= days_remain % 10 <= 4:
        return "дня"
    else:
        return "дней"


@lru_cache(maxsize=None)
def build_event_message(days_remain):
    if days_remain > 0:
        return f"Напоминание о задаче со сроком через {days_remain} {get_days_text(days_remain)}"
    elif days_remain == 0:
        return "Напоминание о задаче со сроком сегодня"
    else:
        return f"Напоминание о просроченной задаче {abs(days_remain)} {get_days_text(abs(days_remain))} назад"


async def notify_everyday_tasks_deadlines():
    now = date.today()
    tomorrow = now + timedelta(days=1)
    date_ranges = [(now + timedelta(days=x)) for x in [3, 7]]

    tasks_query = select(Task).options(
        joinedload(Task.comments).joinedload(Comment.user),
        joinedload(Task.comments).joinedload(Comment.documents)
    ).filter(
        and_(
            or_(
                Task.actual_plan_date.in_(date_ranges),
                Task.actual_plan_date <= tomorrow
            ),
            Task.status.in_(NOTIFICATION_STATUSES)
        )
    ).order_by(Task.actual_plan_date)

    async with async_dbsession() as db:
        tasks = (await db.execute(tasks_query)).scalars().unique().all()

        for task in tasks:
            days_remain = (task.actual_plan_date - now).days
            event_msg = build_event_message(days_remain)

            await send_notify(task, db, event_msg=event_msg, may_edit=False, mark=True)
            await asyncio.sleep(0.1)


async def send_notify(task: Task, db: AsyncSession = None,
                      event_msg: str = "",
                      may_edit=False, mark=False, full_refresh: bool = False):
    async with get_db_safety(db) as db:
        task = await db.merge(task)
        task = await check_task(task, db)
        user_to_notify = task.whom_notify()
        if not user_to_notify:
            logging.warning(f"No relevant user to notify about {task} - {task.description}")
            notifications = await get_notifications(task.id, db=db)
            await delete_notifications(notifications, db)
            return

        text = get_telegram_task_text(task, event_msg)
        notify = {user_to_notify}
        if full_refresh:
            notify.update(await get_notified_users(task.id))
        result = None
        for user in notify:
            target = user.id != user_to_notify.id
            roles = task.get_user_roles_text(user.id)
            roles = roles and f"\n\n<i>Вы: {roles}</i>"
            msg = await send_task_message(f"{text}{roles}", task, user, may_edit=may_edit, no_new=target,
                                          db=db, markup=generate_status_keyboard(user, task))
            if target:
                result = msg
        if mark:
            await notify_sent(task, user_to_notify, db)
        return result


async def notify_when_user_changed(task: Task, old_user: User, new_user: User, role: UserRole, db: AsyncSession = None,
                                   may_edit=True, mark=False):
    async with get_db_safety(db) as db:
        task = await db.merge(task)
        notifications = await get_notifications(task.id, old_user.id, db)
        await delete_notifications(notifications, db)
        await send_notify(task=task, may_edit=may_edit, db=db, mark=mark, full_refresh=True,
                          event_msg=f"{role.value} сменился\n"
                                    f"{old_user.full_name} → {new_user.full_name}")


if __name__ == "__main__":
    asyncio.run(notify_everyday_tasks_deadlines())
