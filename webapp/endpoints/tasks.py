import shutil
import uuid
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from database.models import Task, Statuses, TaskType, Object, User, Comment, Document, CommentType
from webapp.deps import get_db, templates
from webapp.schemas import TaskCreate
import os
router = APIRouter()


@router.get("/add", response_class=HTMLResponse)
async def add_task(request: Request, db: AsyncSession = Depends(get_db)):
    task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
    objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()

    return templates.TemplateResponse("forms/task.html", {
        "request": request,
        "task_types": task_types,
        "objects": objects,
        "users": users,
        "title": "Создание задачи",
        "form_data": {}
    })


@router.post("/add", response_class=HTMLResponse, name="create_task")
async def create_task(
        request: Request,
        task_type_id: int = Form(...),
        object_id: int = Form(...),
        supervisor_id: int = Form(...),
        executor_id: int = Form(...),
        initial_plan_date: date = Form(...),
        description: str = Form(...),
        status: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    user = request.state.user
    status_enum = Statuses.PLANNING if status == 'planning' else Statuses.DRAFT

    task_data = {
        "task_type_id": task_type_id,
        "status": status_enum,
        "object_id": object_id,
        "supplier_id": user.id,
        "supervisor_id": supervisor_id,
        "executor_id": executor_id,
        "initial_plan_date": datetime.combine(initial_plan_date, datetime.min.time()),
        "description": description
    }

    try:
        task_create = TaskCreate(**task_data)
        new_task = Task(**task_create.model_dump())
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
    except (ValidationError, Exception) as e:
        task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
        objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
        users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()
        errors = e.errors() if isinstance(e, ValidationError) else [{"msg": str(e), "loc": ["database"]}]
        return templates.TemplateResponse("forms/task.html", {
            "request": request,
            "task_types": task_types,
            "objects": objects,
            "users": users,
            "title": "Создание задачи",
            "errors": errors,
            "form_data": task_data
        })

    return RedirectResponse(url="/tasks", status_code=303)


@router.get("", response_class=HTMLResponse)
async def list_tasks(request: Request, db: AsyncSession = Depends(get_db)):
    user = request.state.user

    base_query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object),
        joinedload(Task.executor),
        joinedload(Task.supervisor),
        joinedload(Task.supplier)
    )

    supplier_tasks = (await db.execute(
        base_query.filter(Task.supplier_id == user.id, Task.filter_for_supplier())
    )).scalars().all()

    supervisor_tasks = (await db.execute(
        base_query.filter(Task.executor_id == user.id, Task.filter_for_supervisor())
    )).scalars().all()

    executor_tasks = (await db.execute(
        base_query.filter(Task.supervisor_id == user.id, Task.filter_for_executor())
    )).scalars().all()

    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "supplier_tasks": supplier_tasks,
        "supervisor_tasks": supervisor_tasks,
        "executor_tasks": executor_tasks
    })


@router.get("/{task_id}", response_class=HTMLResponse)
async def view_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Task)
        .options(
            joinedload(Task.task_type),
            joinedload(Task.object),
            joinedload(Task.supplier),
            joinedload(Task.supervisor),
            joinedload(Task.executor),
            joinedload(Task.comments).joinedload(Comment.user),
            joinedload(Task.documents),
            joinedload(Task.notifications)
        )
        .filter(Task.id == task_id)
    )

    result = await db.execute(query)
    task = result.unique().scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
    objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()

    is_supplier = request.state.user.id == task.supplier_id

    return templates.TemplateResponse("task_view.html", {
        "request": request,
        "task": task,
        "task_types": task_types,
        "objects": objects,
        "users": users,
        "is_supplier": is_supplier,
        "title": f"Задача {task.id}: {task.task_type.name}"
    })



@router.post("/{task_id}/comment", response_class=HTMLResponse)
async def add_comment(
        request: Request,
        task_id: int,
        comment: str = Form(...),
        files: List[UploadFile] = [],
        db: AsyncSession = Depends(get_db)
):
    user = request.state.user

    if not os.path.exists('documents'):
        os.makedirs('documents')

    new_comment = Comment(
        type=CommentType.comment,
        task_id=task_id,
        user_id=user.id,
        content=comment
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    for file in files:
        uuid_str = str(uuid.uuid4())
        file_path = f"documents/{uuid_str}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        new_document = Document(
            uuid=uuid_str,
            title=file.filename,
            type=file.content_type,
            author_id=user.id
        )
        new_document.comments.append(new_comment)
        db.add(new_document)
        await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/status", response_class=HTMLResponse)
async def update_status(
        request: Request,
        task_id: int,
        new_status: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    user = request.state.user
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        task.update_status(Statuses(new_status))
        db.add(task)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/plan_date", response_class=HTMLResponse)
async def update_plan_date(
        request: Request,
        task_id: int,
        new_plan_date: date = Form(...),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.actual_plan_date = datetime.combine(new_plan_date, datetime.min.time())
    db.add(task)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/cancel", response_class=HTMLResponse)
async def cancel_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.update_status(Statuses.CANCELED)
    db.add(task)
    await db.commit()

    return RedirectResponse(url="/tasks", status_code=303)


@router.get("/{task_id}/duplicate", response_class=HTMLResponse)
async def duplicate_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
    objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()

    return templates.TemplateResponse("forms/task.html", {
        "request": request,
        "task_types": task_types,
        "objects": objects,
        "users": users,
        "title": "Создание задачи",
        "form_data": {
            "task_type_id": task.task_type_id,
            "object_id": task.object_id,
            "supervisor_id": task.supervisor_id,
            "executor_id": task.executor_id,
            "initial_plan_date": task.initial_plan_date,
            "description": task.description
        }
    })


@router.post("/{task_id}/executor", response_class=HTMLResponse)
async def update_executor(
        request: Request,
        task_id: int,
        new_executor_id: int = Form(...),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_executor = await db.get(User, new_executor_id)
    if not new_executor:
        raise HTTPException(status_code=404, detail="Executor not found")

    task.executor_id = new_executor_id
    db.add(task)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/supervisor", response_class=HTMLResponse)
async def update_supervisor(
        request: Request,
        task_id: int,
        new_supervisor_id: int = Form(...),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_supervisor = await db.get(User, new_supervisor_id)
    if not new_supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")

    task.supervisor_id = new_supervisor_id
    db.add(task)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)
