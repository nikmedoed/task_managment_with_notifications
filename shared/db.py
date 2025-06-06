from datetime import date, datetime
from typing import Dict, Sequence
from typing import Optional

from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from database import get_db_safety
from database.models import Task, Comment, TaskType, Object, User, CommentType, TaskNotification, Statuses


async def get_user_by_tg(telegram_id: int, db: AsyncSession = None):
    async with get_db_safety(db) as db:
        result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        return result.scalars().first()


async def get_task_by_id(task_id: int, db: AsyncSession = None) -> Task | None:
    async with get_db_safety(db) as db:
        query = (
            select(Task)
            .options(
                joinedload(Task.task_type),
                joinedload(Task.object),
                joinedload(Task.comments).joinedload(Comment.user),
                joinedload(Task.comments).joinedload(Comment.documents)
            )
            .filter(Task.id == task_id)
        )

        result = await db.execute(query)
        task = result.unique().scalar_one_or_none()
        task.comments.sort(key=lambda x: x.time_created)
        return task


async def get_task_edit_common_data(db: AsyncSession = None):
    async with get_db_safety(db) as db:
        task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
        objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
        users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()
        return {"task_types": task_types, "objects": objects, "users": users}


async def get_user_tasks(user_id: int, db: AsyncSession = None) -> Dict[str, Sequence[Task]]:
    async with get_db_safety(db) as db:
        base_query = select(Task).options(
            joinedload(Task.task_type),
            joinedload(Task.object)
        ).order_by(Task.actual_plan_date)

        supplier_tasks = (await db.execute(
            base_query.filter(Task.supplier_id == user_id, Task.filter_for_supplier())
        )).scalars().all()

        supervisor_tasks = (await db.execute(
            base_query.filter(Task.supervisor_id == user_id, Task.filter_for_supervisor())
        )).scalars().all()

        executor_tasks = (await db.execute(
            base_query.filter(Task.executor_id == user_id, Task.filter_for_executor())
        )).scalars().all()

        return {
            "supplier_tasks": supplier_tasks,
            "supervisor_tasks": supervisor_tasks,
            "executor_tasks": executor_tasks
        }


async def add_error(tid: int, err: str, uid: int = None, db: AsyncSession = None) -> Comment:
    async with get_db_safety(db) as db:
        erc = Comment(type=CommentType.error, task_id=tid, user_id=uid, content=err)
        db.add(erc)
        await db.commit()
        return erc


async def add_comment(task: Task, user: User, comment: str = None, db: AsyncSession = None) -> Comment:
    async with get_db_safety(db) as db:
        new_comment = Comment(
            type=CommentType.comment if comment else CommentType.notified,
            task_id=task.id,
            user_id=user.id,
            author_roles=list(task.get_user_roles(user.id)),
            content=comment
        )
        db.add(new_comment)
        await db.commit()
        return new_comment


async def notify_sent(task: Task, user: User, db: AsyncSession = None) -> Comment:
    async with get_db_safety(db) as db:
        new_comment = Comment(
            type=CommentType.notify_sent,
            task_id=task.id,
            user_id=user.id,
            author_roles=list(task.get_user_roles(user.id))
        )
        db.add(new_comment)
        return new_comment


async def date_change(task: Task, user: User,
                      new_plan_date: date,
                      comment: str = None,
                      user_roles=None,
                      db: AsyncSession = None) -> Comment:
    async with get_db_safety(db) as db:
        task = await db.merge(task)
        if not user_roles:
            user_roles = task.get_user_roles(user.id)
        old_plan_date = task.actual_plan_date
        task.actual_plan_date = new_plan_date
        task.reschedule_count += 1
        new_comment = Comment(
            type=CommentType.date_change,
            task_id=task.id,
            user_id=user.id,
            author_roles=list(user_roles),
            old_date=old_plan_date,
            new_date=task.actual_plan_date,
            content=comment or ""
        )
        db.add(new_comment)
        await db.commit()
        await db.refresh(task)
        return new_comment


async def status_change(task: Task, user: User,
                        new_status: Statuses,
                        comment: str = None,
                        user_roles=None,
                        db: AsyncSession = None) -> Comment | None:
    async with get_db_safety(db) as db:
        task = await db.merge(task)
        if task.status == new_status:
            return
        if not user_roles:
            user_roles = task.get_user_roles(user.id)
        previous_status = task.status
        task.status = new_status
        if new_status == Statuses.REWORK:
            task.rework_count += 1
        new_comment = Comment(
            type=CommentType.status_change,
            task_id=task.id,
            user_id=user.id,
            author_roles=list(user_roles),
            content=comment or "",
            previous_status=previous_status.name,
            new_status=new_status.name
        )
        db.add(new_comment)
        await db.commit()
        await db.refresh(task)
        return new_comment


async def get_notifications(
        task_id: int,
        user_id: Optional[int] = None,
        db: AsyncSession = None
) -> Sequence[TaskNotification]:
    async with get_db_safety(db) as db:
        query = (
            select(TaskNotification)
            .options(selectinload(TaskNotification.user))
            .where(
                and_(
                    TaskNotification.task_id == task_id,
                    TaskNotification.active
                )
            )
        )
        if user_id is not None:
            query = query.where(TaskNotification.user_id == user_id)
        query = query.order_by(TaskNotification.telegram_message_id)

        result = await db.execute(query)
        notifications = result.scalars().all()
        return notifications


async def get_notified_users(
        task_id: int,
        db: AsyncSession = None
) -> Sequence[User]:
    async with get_db_safety(db) as db:
        query = (
            select(User)
            .join(TaskNotification)
            .where(
                and_(
                    TaskNotification.task_id == task_id,
                    TaskNotification.active,
                    TaskNotification.user_id == User.id
                )
            )
            .distinct()
        )
        result = await db.execute(query)
        return result.scalars().all()


async def add_notification(task: Task, user_id: int, message_id: int,
                           db: AsyncSession = None):
    async with get_db_safety(db) as db:
        task = await db.merge(task)
        new_notification = TaskNotification(
            task_id=task.id,
            user_id=user_id,
            telegram_message_id=message_id,
            active=True
        )
        db.add(new_notification)
        task.notification_count += 1
        task.last_notification_date = datetime.now()
        await db.commit()
        await db.refresh(task)
