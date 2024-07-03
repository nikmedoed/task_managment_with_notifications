import os
import urllib.parse
import importlib
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from joserfc import jwt
from joserfc.errors import JoseError
from webapp.endpoints import auth
from webapp.deps import get_db, redis, COOKIE_NAME, BASE_DIR, templates
from database.models import User
from sqlalchemy.future import select
from shared.app_config import app_config
from webapp.endpoints.auth import login

secured_modules = [
    'tasks',
    'users',
    'documents'
]


# ToDo редирект на tasks при неизвестных страницах
# ToDo вывод ошибок

def check_user_acces(request: Request, user: User):
    if not user.active:
        pass
        # Todo Вас удалили. Обратитесь к администратору системы для восстановления аккаунта.
    if not user.verificated:
        pass
        # todo Ваш аккаунт на верификации. Обратитесь к администратору для ускорения верификации.


def create_app() -> FastAPI:
    app = FastAPI()

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    for module_name in secured_modules:
        imported_module = importlib.import_module(f'webapp.endpoints.{module_name}')
        app.include_router(imported_module.router, prefix=f'/{module_name}', tags=[module_name])

    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

    def restricted(path):
        if path == '/':
            return True

        for module_name in secured_modules:
            if path.startswith(f'/{module_name}'):
                return True

        return False

    async def authenticate_user(request: Request):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return

        try:
            token_parts = jwt.decode(token, app_config["telegram"]["jwt_secret_key"])
        except JoseError:
            return

        user_id = token_parts.claims.get('k')

        stored_token = await redis.get(f"{COOKIE_NAME}:{user_id}")
        if not stored_token or stored_token.decode('utf-8') != token:
            return

        async with get_db() as session:
            result = await session.execute(select(User).filter(User.telegram_id == user_id))
            user = result.scalars().first()
            return user

    @app.middleware('http')
    async def middleware(request: Request, call_next):
        if restricted(request.url.path):
            url_safe_path = urllib.parse.quote(request.url.path, safe='')
            user = await authenticate_user(request)
            if not user:
                return await login(request, next_path=url_safe_path)
            if not user.active:
                pass
                # Todo Вас удалили. Обратитесь к администратору системы для восстановления аккаунта.
            if not user.verificated:
                pass
                # todo Ваш аккаунт на верификации. Обратитесь к администратору для ускорения верификации.
            request.state.user = user

        return await call_next(request)

    return app
