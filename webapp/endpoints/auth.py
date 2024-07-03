import hmac
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, HTMLResponse
from joserfc import jwt
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from webapp.deps import get_db, redis, COOKIE_NAME, templates
from shared.app_config import app_config
from database.models import User
from joserfc.errors import JoseError
import hashlib

router = APIRouter()


@router.get('/auth')
@router.get('/login')
async def login(request: Request, next_path=""):
    template_context = {
        'request': request,
        'next_path': next_path,
        'app_config': app_config,
        # "title": "Прайм контроль – авторизация"
    }
    login_wall = templates.TemplateResponse('login.html', template_context)
    return login_wall



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
        if not user.active or not user.verificated:
            # todo общую функцию с мидлварем
            return PlainTextResponse('User is not active or not verified', status_code=403)
        token = jwt.encode({'alg': 'HS256'}, {'k': user_id}, app_config.telegram.jwt_secret_key)
        await redis.set(f"{COOKIE_NAME}:{user_id}", token, ex=3600)
        response = RedirectResponse(next_url)
        response.set_cookie(key=COOKIE_NAME, value=token)
        return response
    else:
        template_context = {
            'request': request,
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'photo_url': photo_url,
            'auth_date': auth_date,
            'next_url': next_url
            # 'title':
        }
        return templates.TemplateResponse('register.html', template_context)


@router.post('/register')
async def register_user(
        request: Request,
        user_id: Annotated[int, Query(alias='id')],
        first_name: Annotated[str, Query(alias='first_name')],
        last_name: Annotated[str, Query(alias='last_name')],
        username: Annotated[str, Query(alias='username')],
        phone_number: Annotated[str, Query(alias='phone_number')],
        position: Annotated[str, Query(alias='position')],
        db: AsyncSession = Depends(get_db)
):
    new_user = User(
        first_name=first_name,
        last_name=last_name,
        telegram_nick=username,
        telegram_id=user_id,
        phone_number=phone_number,
        position=position,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return RedirectResponse("/auth/telegram-callback", status_code=303)


@router.get('/logout')
async def logout(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            token_parts = jwt.decode(token, app_config.telegram.jwt_secret_key)
            user_id = token_parts.claims['k']
            await redis.delete(f"auth-token:{user_id}")
        except JoseError:
            pass

    response = RedirectResponse('/')
    response.delete_cookie(key=COOKIE_NAME)
    return response