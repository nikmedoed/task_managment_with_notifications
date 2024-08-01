from collections import OrderedDict
from datetime import datetime
from io import BytesIO

import openpyxl
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from openpyxl.styles import Alignment
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

    sort_column = getattr(Task, sort_column, Task.time_updated)

    base_query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object)
    )

    count_query = select(func.count(Task.id))

    if status_filter == 'active':
        base_query = base_query.filter(~Task.status.in_(COMPLETED_STATUSES))
        count_query = count_query.filter(~Task.status.in_(COMPLETED_STATUSES))
    elif status_filter == 'completed':
        base_query = base_query.filter(Task.status.in_(COMPLETED_STATUSES))
        count_query = count_query.filter(Task.status.in_(COMPLETED_STATUSES))
    elif status_filter == 'important':
        base_query = base_query.filter(Task.important == True)
        count_query = count_query.filter(Task.important == True)

    if sort_order == 'desc':
        base_query = base_query.order_by(sort_column.desc())
    else:
        base_query = base_query.order_by(sort_column.asc())

    total = await db.scalar(count_query)

    base_query = base_query.offset(offset).limit(page_size)
    result = await db.execute(base_query)
    tasks = result.scalars().all()

    total_all = await db.scalar(select(func.count(Task.id)))
    total_active = await db.scalar(select(func.count(Task.id)).filter(~Task.status.in_(COMPLETED_STATUSES)))
    total_completed = await db.scalar(select(func.count(Task.id)).filter(Task.status.in_(COMPLETED_STATUSES)))
    total_important = await db.scalar(select(func.count(Task.id)).filter(Task.important == True))

    return templates.TemplateResponse("tasks_archive.html", {
        "request": request,
        "tasks": tasks,
        "status_filter": status_filter,
        "sort_column": sort_column.key,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_all": total_all,
        "total_active": total_active,
        "total_completed": total_completed,
        "total_important": total_important
    })


TABLE_EXPORT_COLUMNS = OrderedDict([
    ('id', 'ID'),
    ('task_type.name', 'Тип задачи'),
    ('status.value', 'Статус'),
    ('important', 'Важная'),
    ('object.name', 'Объект'),
    ('supplier.full_name', 'Поставщик'),
    ('supervisor.full_name', 'Руководитель'),
    ('executor.full_name', 'Исполнитель'),
    ('initial_plan_date', 'Начальная плановая дата'),
    ('actual_plan_date', 'Фактическая плановая дата'),
    ('plan_date_shift', 'Перенос'),
    ('last_notification_date', 'Дата последнего увед.'),
    ('description', 'Описание'),
    ('rework_count', 'Количество доработок'),
    ('reschedule_count', 'Количество переназн.'),
    ('notification_count', 'Количество увед.'),
    ('time_created', 'Дата создания'),
    ('time_updated', 'Дата изменения')
])


@router.get("/export", response_class=StreamingResponse, name="export_tasks_to_excel")
async def export_tasks_to_excel(db: AsyncSession = Depends(get_db)):
    query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Все задачи"

    headers = list(TABLE_EXPORT_COLUMNS.values())
    sheet.append(headers)

    for task in tasks:
        row = []
        for col in TABLE_EXPORT_COLUMNS.keys():
            try:
                value = getattr(task, col.split('.')[0], None)
                if '.' in col:
                    nested_attr = col.split('.')[1]
                    value = getattr(value, nested_attr, None)
                if isinstance(value, datetime):
                    if 'date' in col:
                        value = value.strftime("%Y-%m-%d")
                    else:
                        value = value.strftime("%Y-%m-%d %H:%M:%S")
                if value is None:
                    value = ''
            except AttributeError:
                value = ''
            row.append(value)
        sheet.append(row)

    MIN_WIDTH = 10
    for col in sheet.columns:
        max_length = MIN_WIDTH
        column = col[0].column_letter
        for n, cell in enumerate(col):
            cell.alignment = Alignment(wrap_text=True)
            if not n:
                continue
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = max(max_length + 2, MIN_WIDTH)
        sheet.column_dimensions[column].width = adjusted_width

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    response = StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response.headers["Content-Disposition"] = "attachment; filename=tasks.xlsx"
    return response
