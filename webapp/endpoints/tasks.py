import asyncio
import os
import shutil
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from database.db_sessionmaker import get_db
from database.models import Document
from database.models.statuses import *
from shared.db import *
from telegram_bot.routers.statuses import run_status_change
from telegram_bot.utils.notifications import send_notify, notify_when_user_changed
from telegram_bot.utils.send_tasks import broadcast_task
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
        "initial_plan_date": initial_plan_date,
        "description": description,
        "important": important
    }

    try:
        task_create = TaskCreate(**task_data)
        new_task = Task(**task_create.model_dump())
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        if status_enum != Statuses.DRAFT:
            asyncio.ensure_future(send_notify(task=new_task, event_msg="Новая задача"))
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
    permission = task.user_permission(request.state.user.id)
    available_statuses_dict = {status.name: status.value for status in permission.available_statuses}

    return templates.TemplateResponse("task_view.html", {
        "request": request,
        "task": task,
        # **common_data,
        'users': users,
        "Statuses": Statuses,
        "permission": permission,
        "available_statuses": available_statuses_dict,
        "can_change_status": len(permission.available_statuses) > 0,
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
    task: Optional[Task] = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    permission = task.user_permission(request.state.user.id)

    if not permission.can_change_date:
        raise HTTPException(
            status_code=422,
            detail=f"Ваша роль по задаче не позволяет менять дату в текущем статусе ({task.status.value})")

    if permission.must_comment_date and not executor_comment:
        raise HTTPException(status_code=422, detail="Комментарий обязателен для изменения даты исполнителем")

    await date_change(task, request.state.user, new_plan_date, executor_comment, db=db)

    asyncio.ensure_future(send_notify(task=task, may_edit=True, full_refresh=True,
                                      event_msg=f"Смена плановой даты задачи на\n{task.formatted_plan_date}"))
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.get("/{task_id}/duplicate", response_class=HTMLResponse)
async def duplicate_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    task: Optional[Task] = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    user_roles = task.get_user_roles(request.state.user.id)
    if task.status != Statuses.CANCELED:
        if UserRole.SUPPLIER not in user_roles:
            raise HTTPException(status_code=400, detail="Недопустимый переход статуса")
        await status_change(task, request.state.user, Statuses.CANCELED,
                            "Пересоздание задачи", user_roles, db)
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
    task: Optional[Task] = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    new_user: Optional[User] = await db.get(User, new_user_id)
    if not new_user:
        raise HTTPException(status_code=404, detail="Нет такого пользователя")

    user_changed = False

    if role == "executor":
        old_user = task.executor
        role = UserRole.EXECUTOR
        if old_user.id != new_user_id:
            task.executor_id = new_user_id
            user_changed = True
            if task.status not in {Statuses.DRAFT, Statuses.PLANNING} and task.status not in COMPLETED_STATUSES:
                await status_change(task, request.state.user, Statuses.PLANNING,
                                    "Сброс статуса из-за смены исполнителя", db=db)
    elif role == "supervisor":
        old_user = task.supervisor
        role = UserRole.SUPERVISOR
        if old_user.id != new_user_id:
            task.supervisor_id = new_user_id
            user_changed = True
    else:
        raise HTTPException(status_code=400, detail="Некорректная роль")
    await db.commit()
    await db.refresh(task)

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
        await db.commit()
        asyncio.ensure_future(notify_when_user_changed(task=task, old_user=old_user, new_user=new_user, role=role))

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/update_status", response_class=HTMLResponse)
async def update_task_status(
        request: Request,
        task_id: int,
        new_status: str = Form(...),
        status_comment: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    task: Optional[Task] = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    user = request.state.user
    new_status = Statuses[new_status]
    if new_status == Statuses.REWORK:
        task.rework_count += 1

    if new_status in SHOULD_BE_COMMENTED and not status_comment:
        raise HTTPException(status_code=400, detail="Комментарий обязателен для этого статуса")

    user_roles = task.get_user_roles(user.id)
    if not is_valid_transition(task.status, new_status, user_roles):
        raise HTTPException(status_code=400, detail="Недопустимый перевод статуса")

    await db.commit()
    await db.refresh(task)
    previously_notified = task.whom_notify()
    asyncio.ensure_future(run_status_change(task, previously_notified, new_status,
                                            comment=status_comment))

    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)


@router.post("/{task_id}/comment", response_class=HTMLResponse)
async def add_comment_web(
        request: Request,
        task_id: int,
        comment: Optional[str] = Form(None),
        files: List[UploadFile] = None,
        db: AsyncSession = Depends(get_db)
):
    user = request.state.user

    if not os.path.exists('documents'):
        os.makedirs('documents')

    task: Optional[Task] = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if not comment or comment.strip() == "":
        raise HTTPException(status_code=400, detail="Комментарий не может быть пустым")

    new_comment = await add_comment(task, user, comment, db)

    if files:
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
    asyncio.ensure_future(broadcast_task(task, "Новый комментарий по задаче"))
    return RedirectResponse(url=f"/tasks/{task_id}", status_code=303)
