import os
import urllib.parse
import importlib
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from webapp.endpoints import auth, register
from webapp.deps import get_db, redis, BASE_DIR, templates
from database.models import User
from sqlalchemy.future import select
from webapp.errors import error_handlers, render_unactive, render_unverificated
from webapp.titles import SYSTEM_NAME
from database import async_dbsession

secured_modules = [
    'tasks',
    'users',
    'documents'
]


def create_app() -> FastAPI:
    app = FastAPI(
        title=SYSTEM_NAME,
        contact={
            "name": "Muromtsev Nikita",
            "url": "https://t.me/nikmedoed",
            "email": "nikmedoed@gmail.com",
        }
    )

    @app.get("/index.html")
    async def redirect_index():
        return RedirectResponse(url='/')

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(register.router, prefix="/register", tags=["register"])
    for module_name in secured_modules:
        imported_module = importlib.import_module(f'webapp.endpoints.{module_name}')
        app.include_router(imported_module.router, prefix=f'/{module_name}', tags=[module_name])

    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

    def restricted(path) -> bool:
        if path == '/':
            return True

        for module_name in secured_modules:
            if path.startswith(f'/{module_name}'):
                return True

        return False

    @app.middleware('http')
    async def middleware(request: Request, call_next):
        if restricted(request.url.path):
            url_safe_path = urllib.parse.quote(request.url.path, safe='')
            user_id, device_id = await redis.check_token(request)
            if not user_id:
                return await auth.login(request, next_path=url_safe_path)

            async with async_dbsession() as session:
                result = await session.execute(select(User).filter(User.telegram_id == user_id))
                user = result.scalars().first()
            if not user:
                return await auth.login(request, next_path=url_safe_path)

            if not user.active:
                return render_unactive(request)
            if not user.verificated:
                return render_unverificated(request)
            request.state.user = user

        return await call_next(request)

    error_handlers(app)

    return app
