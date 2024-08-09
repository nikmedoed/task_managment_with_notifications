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
from database.models.statuses import COMPLETED_STATUSES, Statuses
from webapp.deps import get_db, templates

router = APIRouter()

tab_filters = {
    'active': {'name': 'Активные', 'filter': ~Task.status.in_(COMPLETED_STATUSES)},
    'important': {'name': 'Важные', 'filter': Task.important == True},
    'completed': {'name': 'Завершенные', 'filter': Task.status == Statuses.DONE},
    'canceled': {'name': 'Отмененные', 'filter': Task.status == Statuses.CANCELED},
    'all': {'name': 'Все', 'filter': True}
}


@router.get("", response_class=HTMLResponse)
async def task_archive(
        request: Request,
        status_filter: str = Query('active'),
        sort_column: str = Query('time_updated'),
        sort_order: str = Query('desc'),
        page: int = Query(1, ge=1),
        page_size: int = Query(30, ge=1),
        db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size
    sort_column_attr = getattr(Task, sort_column, Task.time_updated)

    filter_condition = tab_filters[status_filter]['filter']
    base_query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object)
    ).filter(filter_condition)

    count_query = select(func.count(Task.id)).filter(filter_condition)
    base_query = base_query.order_by(sort_column_attr.desc() if sort_order == 'desc' else sort_column_attr.asc())
    base_query = base_query.offset(offset).limit(page_size)

    result = await db.execute(base_query)
    tasks = result.scalars().all()

    total = await db.scalar(count_query)

    tab_data = {}
    for key, value in tab_filters.items():
        total_count = await db.scalar(select(func.count(Task.id)).filter(value['filter']))
        tab_data[key] = {'name': value['name'], 'count': total_count}

    return templates.TemplateResponse("tasks_archive.html", {
        "request": request,
        "tasks": tasks,
        "status_filter": status_filter,
        "sort_column": sort_column,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
        "total": total,
        "tab_data": tab_data
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
