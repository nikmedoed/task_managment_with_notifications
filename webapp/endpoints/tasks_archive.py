# tasks_archive.py
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
from starlette.responses import HTMLResponse

from database.models import Task
from database.models.statuses import COMPLETED_STATUSES
from webapp.deps import get_db, templates

router = APIRouter()

@router.get("", response_class=HTMLResponse)
async def task_archive(
        request: Request,
        status_filter: str = Query('all'),
        sort_column: str = Query('time_updated'),  # Default to time_updated
        sort_order: str = Query('desc'),  # Default sort order to desc
        page: int = Query(1, ge=1),
        page_size: int = Query(30, ge=1),
        db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size

    # Ensure the sort column is a valid attribute of Task
    valid_sort_columns = {
        'time_created': Task.time_created,
        'time_updated': Task.time_updated,  # Added time_updated for sorting
        'description': Task.description,
        'task_type_id': Task.task_type_id,
        'object_id': Task.object_id,
        'supplier_id': Task.supplier_id,
        'executor_id': Task.executor_id,
        'supervisor_id': Task.supervisor_id,
        'status': Task.status
    }

    sort_column = valid_sort_columns.get(sort_column, Task.time_updated)

    base_query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object),
        joinedload(Task.supplier),
        joinedload(Task.executor),
        joinedload(Task.supervisor)
    )

    if status_filter == 'active':
        base_query = base_query.filter(~Task.status.in_(COMPLETED_STATUSES))
    elif status_filter == 'completed':
        base_query = base_query.filter(Task.status.in_(COMPLETED_STATUSES))

    # Apply sorting
    if sort_order == 'desc':
        base_query = base_query.order_by(sort_column.desc())
    else:
        base_query = base_query.order_by(sort_column.asc())

    base_query = base_query.offset(offset).limit(page_size)
    result = await db.execute(base_query)
    tasks = result.scalars().all()

    # Calculate counts for each filter type
    total_all = await db.scalar(select(func.count(Task.id)))
    total_active = await db.scalar(select(func.count(Task.id)).filter(~Task.status.in_(COMPLETED_STATUSES)))
    total_completed = await db.scalar(select(func.count(Task.id)).filter(Task.status.in_(COMPLETED_STATUSES)))

    count_query = select(func.count(Task.id))
    total = (await db.execute(count_query)).scalar()

    return templates.TemplateResponse("tasks_archive.html", {
        "request": request,
        "tasks": tasks,
        "status_filter": status_filter,
        "sort_column": sort_column.key,  # Используйте .key для получения имени колонки
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_all": total_all,
        "total_active": total_active,
        "total_completed": total_completed
    })
