import urllib.parse

from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from joserfc import jwt
from joserfc.errors import JoseError

from webapp.auth import auth_router
from shared.app_config import app_config
from database import db_sessionmaker
from database.models import User


redis = app_config.redis.create_connector()
app = FastAPI()
templates = Jinja2Templates('src/templates')

app.mount('/auth', auth_router)

COOKIE_NAME = 'auth-token'


async def get_db():
    async with db_sessionmaker() as session:
        yield session


@app.middleware('http')
async def middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/auth/'):
        return response

    url_safe_path = urllib.parse.quote(request.url.path, safe='')
    template_context = {'request': request, 'next_path': url_safe_path}
    login_wall = templates.TemplateResponse('login.html', template_context)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return login_wall

    try:
        token_parts = jwt.decode(token, app_config.telegram.jwt_secret_key)
    except JoseError:
        return login_wall

    user_id = token_parts.claims['k']

    stored_token = await redis.get(f"auth-token:{user_id}")
    if stored_token != token:
        return login_wall

    async with get_db() as session:
        user = await session.execute(select(User).filter(User.telegram_id == user_id))
        user = user.scalars().first()
        if not user or not user.active or not user.verificated:
            return login_wall

    return response
