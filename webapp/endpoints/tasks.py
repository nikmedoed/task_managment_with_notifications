import os
import shutil
import uuid
from datetime import date
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from database.models import Task, Comment, CommentType, Document
from database.models import User
from database.models.statuses import *
from shared.db import get_task_by_id, get_task_edit_common_data, get_user_tasks
from webapp.deps import templates
from webapp.schemas import TaskCreate

router = APIRouter()


@router.get("/add", response_class=HTMLResponse)
async def add_task(request: Request, db: AsyncSession = Depends(get_db)):
    common_data = await get_task_edit_common_data(db)
    return templates.TemplateResponse("forms/task.html", {
        "request": request,
        "title": "Создание задачи",
        "form_data": {},
        **common_data
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
        important: bool = Form(False),
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
        "description": description,
        "important": important
    }

    try:
        task_create = TaskCreate(**task_data)
        new_task = Task(**task_create.model_dump())
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
    except (ValidationError, Exception) as e:
        common_data = await get_task_edit_common_data(db)
        errors = e.errors() if isinstance(e, ValidationError) else [{"msg": str(e), "loc": ["database"]}]
        return templates.TemplateResponse("forms/task.html", {
            "request": request,
            "title": "Создание задачи",
            "errors": errors,
            "form_data": task_data,
            **common_data
        })

    return RedirectResponse(url="/tasks", status_code=303)


@router.get("", response_class=HTMLResponse)
async def list_tasks(request: Request, db: AsyncSession = Depends(get_db)):
    user = request.state.user
    tasks = await get_user_tasks(user.id, db)

    return templates.TemplateResponse("tasks.html", {
        "request": request,
        **tasks
    })


@router.get("/{task_id}", response_class=HTMLResponse)
async def view_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_task_by_id(task_id, db)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # common_data = await get_task_edit_common_data(db)
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()
    user_roles = task.get_user_roles(request.state.user.id)

    available_statuses = {status for role in user_roles for status in
                          ROLE_STATUS_TRANSITIONS.get(role, {}).get(task.status, set())}
    available_statuses_dict = {status.name: status.value for status in available_statuses}

    return templates.TemplateResponse("task_view.html", {
        "request": request,
        "task": task,
        # **common_data,
        'users': users,
        "is_supplier": UserRole.SUPPLIER in user_roles,
        "is_executor": UserRole.EXECUTOR in user_roles,
        "is_supervisor": UserRole.SUPERVISOR in user_roles,
        "Statuses": Statuses,
        "available_statuses": available_statuses_dict,
        "can_change_status": len(available_statuses) > 0,
        "title": f"Задача {task.id}: {task.task_type.name}",
        "CommentType": CommentType
    })


@router.post("/{task_id}/plan_date", response_class=HTMLResponse)
async def update_plan_date(
        request: Request, task_id: int,
        new_plan_date: date = Form(...),
        executor_comment: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    roles = task.get_user_roles(request.state.user.id)
    if UserRole.EXECUTOR in roles:
        if not executor_comment:
            raise HTTPException(status_code=400, detail="Комментарий обязателен для изменения даты исполнителем")

    old_plan_date = task.actual_plan_date
    task.actual_plan_date = new_plan_date
    task.reschedule_count += 1
    db.add(task)
    new_comment = Comment(
        type=CommentType.date_change,
        task_id=task.id,
        user_id=request.state.user.id,
        author_roles=list(roles),
        old_date=old_plan_date,
        new_date=task.actual_plan_date,
        content=executor_comment or ""
    )
    db.add(new_comment)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.get("/{task_id}/duplicate", response_class=HTMLResponse)
async def duplicate_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if task.status != Statuses.CANCELED:
        if UserRole.SUPPLIER not in task.get_user_roles(request.state.user.id):
            raise HTTPException(status_code=400, detail="Недопустимый переход статуса")
        task.status = Statuses.CANCELED
        await db.commit()
    await task.set_cancel_if_not(db)
    common_data = await get_task_edit_common_data(db)
    return templates.TemplateResponse("forms/task.html", {
        "request": request,
        **common_data,
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


@router.post("/{task_id}/update_role/{role}", response_class=HTMLResponse)
async def update_role(
        request: Request, task_id: int, role: str, new_user_id: int = Form(...),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    new_user = await db.get(User, new_user_id)
    if not new_user:
        raise HTTPException(status_code=404, detail="Нет такого пользователя")

    old_user = None
    user_changed = False

    if role == "executor":
        old_user = task.executor
        if old_user.id != new_user_id:
            task.executor_id = new_user_id
            user_changed = True
            if task.status not in {Statuses.DRAFT, Statuses.PLANNING} and task.status not in COMPLETED_STATUSES:
                previous_status = task.status
                task.status = Statuses.PLANNING
                status_change_comment = Comment(
                    type=CommentType.status_change,
                    task_id=task.id,
                    user_id=request.state.user.id,
                    author_roles=list(task.get_user_roles(request.state.user.id)),
                    previous_status=previous_status.name,
                    new_status=Statuses.PLANNING.name
                )
                db.add(status_change_comment)
    elif role == "supervisor":
        old_user = task.supervisor
        if old_user.id != new_user_id:
            task.supervisor_id = new_user_id
            user_changed = True
    else:
        raise HTTPException(status_code=400, detail="Некорректная роль")

    if user_changed:
        user_change_comment = Comment(
            type=CommentType.user_change,
            task_id=task.id,
            user_id=request.state.user.id,
            author_roles=list(task.get_user_roles(request.state.user.id)),
            extra_data={
                "role": role,
                "old_user": {
                    "id": old_user.id,
                    "name": old_user.full_name,
                    "position": old_user.position
                },
                "new_user": {
                    "id": new_user.id,
                    "name": new_user.full_name,
                    "position": new_user.position
                }
            }
        )
        db.add(user_change_comment)

    db.add(task)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/update_status", response_class=HTMLResponse)
async def update_task_status(
        request: Request,
        task_id: int,
        new_status: str = Form(...),
        status_comment: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    user = request.state.user
    status_enum = Statuses[new_status]
    if status_enum == Statuses.REWORK:
        task.rework_count += 1

    previous_status = task.status

    if status_enum in {Statuses.REWORK, Statuses.REJECTED} and not status_comment:
        raise HTTPException(status_code=400, detail="Комментарий обязателен для этого статуса")

    user_roles = task.get_user_roles(user.id)
    if not is_valid_transition(task.status, status_enum, user_roles):
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса")
    task.status = status_enum

    new_comment = Comment(
        type=CommentType.status_change,
        task_id=task.id,
        user_id=user.id,
        author_roles=list(user_roles),
        content=status_comment or "",
        previous_status=previous_status.name,
        new_status=status_enum.name
    )
    db.add(new_comment)

    db.add(task)
    await db.commit()

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/comment", response_class=HTMLResponse)
async def add_comment(
        request: Request,
        task_id: int,
        comment: Optional[str] = Form(None),
        files: List[UploadFile] = [],
        db: AsyncSession = Depends(get_db)
):
    user = request.state.user

    if not os.path.exists('documents'):
        os.makedirs('documents')

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if not comment or comment.strip() == "":
        raise HTTPException(status_code=400, detail="Комментарий не может быть пустым")

    new_comment = Comment(
        type=CommentType.comment,
        task_id=task_id,
        user_id=user.id,
        author_roles=list(task.get_user_roles(request.state.user.id)),
        content=comment,
        new_date=datetime.utcnow()
    )
    db.add(new_comment)
    await db.flush()

    for file in files:
        if file.filename:
            uuid_str = str(uuid.uuid4())
            file_path = f"documents/{uuid_str}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            new_document = Document(
                uuid=uuid_str,
                title=file.filename,
                type=file.content_type,
                author_id=user.id,
                comment_id=new_comment.id
            )
            db.add(new_document)

    await db.commit()
    await db.refresh(new_comment)
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)
