import hmac
from typing import Annotated

from fastapi import APIRouter, Query, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from webapp.deps import get_db, redis, templates
from webapp.utils.RedisStore import COOKIE_AUTH
from shared.app_config import app_config
from database.models import User
import hashlib
from uuid import uuid4

router = APIRouter()


@router.get('')
@router.get('/login')
async def login(request: Request, next_path=""):
    template_context = {
        'request': request,
        'next_path': next_path,
        'app_config': app_config
    }
    login_wall = templates.TemplateResponse('login.html', template_context)
    return login_wall


# todo общую функцию проверки активности пользователя с мидлварем

@router.get('/telegram-callback')
async def telegram_callback(
        request: Request,
        user_id: Annotated[int, Query(alias='id')],
        query_hash: Annotated[str, Query(alias='hash')],
        username: Annotated[str, Query(alias='username')],
        first_name: Annotated[str, Query(alias='first_name')],
        auth_date: Annotated[int, Query(alias='auth_date')],
        last_name: Annotated[str, Query(alias='last_name')] = '',
        photo_url: Annotated[str, Query(alias='photo_url')] = '',
        next_url: Annotated[str, Query(alias='next')] = '/',
        db: AsyncSession = Depends(get_db),
):
    params = request.query_params.items()
    data_check_string = '\n'.join(sorted(f'{x}={y}' for x, y in params if x not in ('hash', 'next')))
    secret_key = hashlib.sha256(app_config.telegram.token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    is_correct = hmac.compare_digest(computed_hash, query_hash)
    if not is_correct:
        return PlainTextResponse('Authorization failed. Please try again', status_code=401)

    result = await db.execute(select(User).filter(User.telegram_id == user_id))
    user = result.scalars().first()
    if user:
        response = RedirectResponse(next_url)
    else:
        session_data = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'photo_url': photo_url,
            'auth_date': auth_date,
            'next_url': next_url
        }
        await redis.set_register_data(user_id, session_data)
        response = RedirectResponse('/register')
    device_id = str(uuid4())
    await redis.set_token(user_id, device_id, response)
    return response


@router.get('/logout')
async def logout(request: Request):
    user_id, device_id = await redis.check_token(request)
    if user_id:
        redis.delete_token(user_id, device_id)
    response = RedirectResponse('/')
    response.delete_cookie(key=COOKIE_AUTH)
    return response
