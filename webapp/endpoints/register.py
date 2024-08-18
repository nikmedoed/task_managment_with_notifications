import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models import User
from webapp.deps import redis, templates
from database import get_db
from webapp.utils.RedisStore import REDIS_KEY_USER_REGISTER
from sqlalchemy import func

router = APIRouter()


@router.get('')
async def get_register(
        request: Request
):
    user_id, device_id = await redis.check_token(request)
    if not user_id:
        return RedirectResponse('/auth', status_code=303)

    session_data = await redis.get(f"{REDIS_KEY_USER_REGISTER}:{user_id}")
    if not session_data:
        return RedirectResponse('/auth', status_code=303)

    session_data = json.loads(session_data)

    template_context = {
        'request': request,
        'user_id': user_id,
        'username': session_data['username'],
        'first_name': session_data['first_name'],
        'last_name': session_data['last_name'],
        'photo_url': session_data['photo_url'],
        'auth_date': session_data['auth_date'],
        'next_url': session_data['next_url']
    }
    return templates.TemplateResponse('register.html', template_context)


@router.post('')
async def register_user(
        request: Request,
        user_id: Annotated[int, Form()],
        first_name: Annotated[str, Form()],
        last_name: Annotated[str, Form()],
        position: Annotated[str, Form()],
        middle_name: Annotated[str, Form()] = '',
        email: Annotated[str, Form()] = '',
        username: Annotated[str, Form()] = '',
        phone_number: Annotated[str, Form()] = '',
        next_url: Annotated[str, Form()] = '/',
        db: AsyncSession = Depends(get_db)
):
    t_user_id, device_id = await redis.check_token(request)
    print("user reg post", t_user_id, device_id)
    if not t_user_id or t_user_id != user_id:
        return RedirectResponse('/auth', status_code=303)

    result = await db.execute(select(User).filter(User.telegram_id == user_id))
    user = result.scalars().first()

    if user:
        user.first_name = first_name
        user.last_name = last_name
        user.middle_name = middle_name
        user.email = email
        user.telegram_nick = username
        user.phone_number = phone_number
        user.position = position
    else:
        user = User(
            telegram_id=user_id,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            email=email,
            telegram_nick=username,
            phone_number=phone_number,
            position=position,
        )
        user_count = await db.scalar(select(func.count(User.id)))
        if user_count < 3:
            user.verificated = True
            user.active = True
            user.admin = True
        db.add(user)

    await db.commit()
    await db.refresh(user)
    response = RedirectResponse(next_url, status_code=303)
    await redis.set_token(user_id, device_id, response)
    return response
