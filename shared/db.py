from typing import Dict, Sequence

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models import Task, Comment, TaskType, Object, User


async def get_user_by_tg(telegram_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    return result.scalars().first()


async def get_task_by_id(task_id: int, db: AsyncSession = Depends(get_db)):
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
    task.comments.sort(key=lambda x: x.time_updated, reverse=True)
    return task


async def get_task_edit_common_data(db: AsyncSession):
    task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
    objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()
    return {"task_types": task_types, "objects": objects, "users": users}


async def get_user_tasks(user_id: int, db: AsyncSession = Depends(get_db)) -> Dict[str, Sequence[Task]]:
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
