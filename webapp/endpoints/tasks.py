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
from sqlalchemy.orm import joinedload

from database.models import Task, Comment, CommentType, Document
from database.models import TaskType, Object, User
from database.models.statuses import *
from webapp.deps import get_db
from webapp.deps import templates
from webapp.schemas import TaskCreate

router = APIRouter()


async def get_common_data(db: AsyncSession):
    task_types = (await db.execute(select(TaskType).filter(TaskType.active == True))).scalars().all()
    objects = (await db.execute(select(Object).filter(Object.active == True))).scalars().all()
    users = (await db.execute(select(User).filter(User.active == True).order_by(User.last_name))).scalars().all()
    return {"task_types": task_types, "objects": objects, "users": users}


@router.get("/add", response_class=HTMLResponse)
async def add_task(request: Request, db: AsyncSession = Depends(get_db)):
    common_data = await get_common_data(db)
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
        common_data = await get_common_data(db)
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

    base_query = select(Task).options(
        joinedload(Task.task_type),
        joinedload(Task.object)
    )

    supplier_tasks = (await db.execute(
        base_query.filter(Task.supplier_id == user.id, Task.filter_for_supplier())
    )).scalars().all()

    supervisor_tasks = (await db.execute(
        base_query.filter(Task.supervisor_id == user.id, Task.filter_for_supervisor())
    )).scalars().all()

    executor_tasks = (await db.execute(
        base_query.filter(Task.executor_id == user.id, Task.filter_for_executor())
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
            joinedload(Task.comments).joinedload(Comment.user),
            joinedload(Task.comments).joinedload(Comment.documents)
        )
        .filter(Task.id == task_id)
    )

    result = await db.execute(query)
    task = result.unique().scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    common_data = await get_common_data(db)
    user_roles = get_user_roles(request.state.user, task)

    available_statuses = {status for role in user_roles for status in
                          ROLE_STATUS_TRANSITIONS.get(role, {}).get(task.status, set())}
    available_statuses_dict = {status.name: status.value for status in available_statuses}

    task.comments.sort(key=lambda x: x.time_updated, reverse=True)

    return templates.TemplateResponse("task_view.html", {
        "request": request,
        "task": task,
        **common_data,
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
        request: Request, task_id: int, new_plan_date: date = Form(...),
        db: AsyncSession = Depends(get_db)
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    old_plan_date = task.actual_plan_date
    task.actual_plan_date = new_plan_date
    task.reschedule_count += 1
    db.add(task)
    new_comment = Comment(
        type=CommentType.date_change,
        task_id=task.id,
        user_id=request.state.user.id,
        author_roles=list(get_user_roles(request.state.user, task)),
        old_date=old_plan_date,
        new_date=task.actual_plan_date
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
        if UserRole.SUPPLIER not in get_user_roles(request.state.user, task):
            raise HTTPException(status_code=400, detail="Недопустимый переход статуса")
        task.status = Statuses.CANCELED
        await db.commit()
    await task.set_cancel_if_not(db)
    common_data = await get_common_data(db)
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

    if role == "executor":
        old_user = task.executor
        if old_user.id != new_user_id:
            task.executor_id = new_user_id
            if task.status not in {Statuses.DRAFT, Statuses.PLANNING} and task.status not in COMPLETED_STATUSES:
                previous_status = task.status
                task.status = Statuses.PLANNING
                status_change_comment = Comment(
                    type=CommentType.status_change,
                    task_id=task.id,
                    user_id=request.state.user.id,
                    author_roles=list(get_user_roles(request.state.user, task)),
                    previous_status=previous_status.name,
                    new_status=Statuses.PLANNING.name
                )
                db.add(status_change_comment)

            user_change_comment = Comment(
                type=CommentType.user_change,
                task_id=task.id,
                user_id=request.state.user.id,
                author_roles=list(get_user_roles(request.state.user, task)),
                extra_data={
                    "role": role,
                    "old_user": {
                        "id": old_user.id,
                        "name": f"{old_user.last_name} {old_user.first_name} {old_user.middle_name}",
                        "position": old_user.position
                    },
                    "new_user": {
                        "id": new_user.id,
                        "name": f"{new_user.last_name} {new_user.first_name} {new_user.middle_name}",
                        "position": new_user.position
                    }
                }
            )
            db.add(user_change_comment)
    elif role == "supervisor":
        old_user = task.supervisor
        if old_user.id != new_user_id:
            task.supervisor_id = new_user_id

            user_change_comment = Comment(
                type=CommentType.user_change,
                task_id=task.id,
                user_id=request.state.user.id,
                author_roles=list(get_user_roles(request.state.user, task)),
                extra_data={
                    "role": role,
                    "old_user": {
                        "id": old_user.id,
                        "name": f"{old_user.last_name} {old_user.first_name} {old_user.middle_name}",
                        "position": old_user.position
                    },
                    "new_user": {
                        "id": new_user.id,
                        "name": f"{new_user.last_name} {new_user.first_name} {new_user.middle_name}",
                        "position": new_user.position
                    }
                }
            )
            db.add(user_change_comment)
    else:
        raise HTTPException(status_code=400, detail="Некорректная роль")

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

    user_roles = get_user_roles(user, task)
    if not is_valid_transition(task.status, status_enum, user_roles):
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса")
    task.status = status_enum
    if status_comment:
        new_comment = Comment(
            type=CommentType.status_change,
            task_id=task.id,
            user_id=user.id,
            author_roles=list(get_user_roles(request.state.user, task)),
            content=status_comment,
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
        author_roles=list(get_user_roles(request.state.user, task)),
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


def get_user_roles(user, task):
    roles = set()
    if user.id == task.supplier_id:
        roles.add(UserRole.SUPPLIER)
    if user.id == task.executor_id:
        roles.add(UserRole.EXECUTOR)
    if user.id == task.supervisor_id:
        roles.add(UserRole.SUPERVISOR)
    if not roles:
        roles.add(UserRole.GUEST)
    return roles
