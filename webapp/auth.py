import hmac
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from joserfc import jwt

from shared.app_config import app_config
from database import db_sessionmaker
from database.models import User

redis = app_config.redis.create_connector()
auth_router = APIRouter()

COOKIE_NAME = 'auth-token'


async def get_db():
    async with db_sessionmaker() as session:
        yield session


@auth_router.get('/telegram-callback')
async def telegram_callback(
        request: Request,
        user_id: Annotated[int, Query(alias='id')],
        query_hash: Annotated[str, Query(alias='hash')],
        first_name: Annotated[str, Query(alias='first_name')],
        last_name: Annotated[str, Query(alias='last_name', default='')],
        username: Annotated[str, Query(alias='username')],
        next_url: Annotated[str, Query(alias='next')] = '/',
        db: db_sessionmaker = Depends(get_db),
):
    params = request.query_params.items()
    data_check_string = '\n'.join(sorted(f'{x}={y}' for x, y in params if x not in ('hash', 'next')))
    computed_hash = hmac.new(app_config.telegram.token.encode(), data_check_string.encode(), 'sha256').hexdigest()
    is_correct = hmac.compare_digest(computed_hash, query_hash)
    if not is_correct:
        return PlainTextResponse('Authorization failed. Please try again', status_code=401)

    async with db() as session:
        user = await session.execute(select(User).filter(User.telegram_id == user_id))
        user = user.scalars().first()
        if user:
            if not user.active or not user.verificated:
                return PlainTextResponse('User is not active or not verified', status_code=403)
        else:
            new_user = User(
                first_name=first_name,
                last_name=last_name,
                telegram_nick=username,
                telegram_id=user_id,
                phone_number='',  # Можно обновить позже
                position=''  # Можно обновить позже
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

    token = jwt.encode({'alg': 'HS256'}, {'k': user_id}, app_config.telegram.jwt_secret_key)
    await redis.set(f"auth-token:{user_id}", token, ex=3600)  # Срок действия токена 1 час
    response = RedirectResponse(next_url)
    response.set_cookie(key=COOKIE_NAME, value=token)
    return response


@auth_router.get('/logout')
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
