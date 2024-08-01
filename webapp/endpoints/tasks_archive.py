from io import BytesIO

import openpyxl
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func
from starlette.responses import HTMLResponse

from database.models import Task
from database.models.statuses import COMPLETED_STATUSES
from webapp.deps import get_db, templates

router = APIRouter()

COLUMN_INTERFACE = {
    'id': 'ID',
    'time_updated': 'Дата изменения',
    'description': 'Описание',
    'task_type_id': 'Тип',
    'object_id': 'Объект',
    'supplier_id': 'Постановщик',
    'supervisor_id': 'Руководитель',
    'executor_id': 'Исполнитель',
    'status': 'Статус'
}


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

    sort_column = getattr(Task, sort_column, Task.time_updated)

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

    if sort_order == 'desc':
        base_query = base_query.order_by(sort_column.desc())
    else:
        base_query = base_query.order_by(sort_column.asc())

    base_query = base_query.offset(offset).limit(page_size)
    result = await db.execute(base_query)
    tasks = result.scalars().all()

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
        "total_completed": total_completed,
        'column_names': COLUMN_INTERFACE
    })


@router.get("/export", response_class=StreamingResponse, name="export_tasks_to_excel")
async def export_tasks_to_excel(db: AsyncSession = Depends(get_db)):
    # Fetch all tasks
    query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object),
        joinedload(Task.supplier),
        joinedload(Task.executor),
        joinedload(Task.supervisor)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Tasks"

    headers = [
        "ID", "Description", "Task Type", "Object", "Supplier",
        "Supervisor", "Executor", "Status", "Time Created", "Time Updated"
    ]
    sheet.append(headers)

    for task in tasks:
        row = [
            task.id,
            task.description,
            task.task_type.name,
            task.object.name,
            f"{task.supplier.first_name} {task.supplier.last_name}",
            f"{task.supervisor.first_name} {task.supervisor.last_name}",
            f"{task.executor.first_name} {task.executor.last_name}",
            task.status.value,
            task.time_created.strftime("%Y-%m-%d %H:%M:%S"),
            task.time_updated.strftime("%Y-%m-%d %H:%M:%S")
        ]
        sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    response = StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = "attachment; filename=tasks.xlsx"
    return response
