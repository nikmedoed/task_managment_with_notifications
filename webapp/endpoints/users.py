import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, Response
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from database.models import User
from telegram_bot.utils.get_user_photo import get_user_avatar
from webapp.deps import templates
from webapp.schemas import UserSchema
from webapp.utils.save_avatar import AVATAR_DIR, save_avatar_to_disk

router = APIRouter()

CACHE_DURATION = timedelta(days=1)


@router.get("/avatar")
@router.get("/{user_id:int}/avatar")
async def avatar_endpoint(request: Request, user_id: int = None,
                          background_tasks: BackgroundTasks = BackgroundTasks(),
                          db: AsyncSession = Depends(get_db)):
    user = request.state.user
    if user_id:
        user = await db.get(User, user_id)
        if not user:
            # Возвращаем 204 (No Content), если пользователь не найден, вместо исключения
            return Response(status_code=204)

    avatar_path = AVATAR_DIR / f"{user.id}.jpg"

    if avatar_path.exists():
        file_modified_time = datetime.fromtimestamp(avatar_path.stat().st_mtime)
        headers = {
            'Cache-Control': f'public, max-age={CACHE_DURATION.total_seconds()}',
            'Last-Modified': file_modified_time.strftime('%a, %d %b %Y %H:%M:%S GMT')
        }
        background_tasks.add_task(save_avatar_to_disk, user)
        return FileResponse(avatar_path, headers=headers)

    avatar_data = await get_user_avatar(user.telegram_id)
    if avatar_data:
        background_tasks.add_task(save_avatar_to_disk, user)
        return StreamingResponse(io.BytesIO(avatar_data), media_type="image/jpeg")

    # Если аватар не найден, возвращаем 204 (No Content)
    return Response(status_code=204)


@router.get("", response_class=HTMLResponse)
async def list_users(request: Request, db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).order_by(text('last_name, first_name, middle_name')))).scalars().all()
    unverified_users = []
    verified_users = []
    for user in users:
        if not user.verificated and user.active:
            unverified_users.append(user)
        else:
            verified_users.append(user)
    return templates.TemplateResponse("users.html", {
        "request": request,
        "unverified_users": unverified_users,
        "users": verified_users
    })


@router.get("/profile", response_class=HTMLResponse)
@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user(request: Request, user_id: int = None, db: AsyncSession = Depends(get_db)):
    current_user = request.state.user
    if user_id:
        if not current_user.admin and current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit other users")
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        user = current_user
    return templates.TemplateResponse("forms/user.html", {"request": request, "user": user})


@router.post("/profile", response_class=HTMLResponse)
@router.post("/{user_id}/edit", response_class=HTMLResponse)
async def save_user(request: Request, user_id: int = None, db: AsyncSession = Depends(get_db)):
    current_user = request.state.user

    if user_id:
        if not current_user.admin and current_user.id != user_id:
            raise HTTPException(status_code=403,
                                detail="Неавторизованный доступ. Вы не можете редактировать данное поле.")
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден.")
    else:
        user_id = current_user.id

    form_data = await request.form()
    form_dict = {k: v for k, v in form_data.items()}

    if not current_user.admin:
        restricted_fields = ['admin', 'verificated', 'active']
        for field in restricted_fields:
            if field in form_dict:
                raise HTTPException(status_code=403, detail=f"Вам не доступно изменение поля {field}")

    try:
        user_data = UserSchema(**form_dict)
    except ValidationError as e:
        return templates.TemplateResponse(
            "forms/user.html",
            {"request": request, "user": form_dict, "errors": e.errors()}
        )

    user = await db.get(User, user_id) if user_id else User(**user_data.model_dump())
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    for key, value in user_data.model_dump().items():
        setattr(user, key, value)
    if not user_id:
        db.add(user)
    await db.commit()
    await db.refresh(user)
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/{action}", response_class=HTMLResponse)
async def user_action(request: Request, user_id: int, action: str, db: AsyncSession = Depends(get_db)):
    current_user = request.state.user
    if not current_user.admin:
        raise HTTPException(status_code=403, detail="Not authorized to perform this action")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if action == "verify":
        user.verificated = True
    elif action == "block":
        user.active = False
    elif action == "restore":
        user.active = True
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.commit()
    return RedirectResponse(url="/users", status_code=303)
