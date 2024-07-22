import importlib
import inspect
import os
import urllib.parse

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.responses import HTMLResponse, RedirectResponse
import webapp.filters
from database import async_dbsession
from database.models import User
from webapp.deps import get_db
from webapp.deps import get_db, redis, BASE_DIR, templates, generate_static_template
from webapp.endpoints import auth, register, tasks
from webapp.endpoints import tasks
from webapp.errors import error_handlers, render_unactive, render_unverificated

SYSTEM_NAME = "Прайм контроль"

modules = {
    'auth': {'name': 'Авторизация'},
    'register': {'name': 'Регистрация'},
    'tasks': {'name': 'Мои задачи', 'icon': 'card-checklist', 'secured': True},
    'users': {'name': 'Пользователи', 'icon': 'people', 'secured': True},
    'documents': {'name': 'Документы', 'icon': 'file-earmark-text', 'secured': True},
    'references': {'name': 'Справочники', 'icon': 'journal-bookmark', 'secured': True},
}

secured_modules = {k: v for k, v in modules.items() if v.get('secured')}

templates.env.globals['secured_modules'] = secured_modules
templates.env.globals['SYSTEM_NAME'] = SYSTEM_NAME
for name, func in inspect.getmembers(webapp.filters, inspect.isfunction):
    templates.env.filters[name] = func


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

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request, db: AsyncSession = Depends(get_db)):
        return await tasks.list_tasks(request, db)

    for module_name in modules:
        imported_module = importlib.import_module(f'webapp.endpoints.{module_name}')
        app.include_router(imported_module.router, prefix=f'/{module_name}', tags=[module_name])
        generate_static = getattr(imported_module, 'generate_static', None)
        if generate_static:
            for args in generate_static():
                generate_static_template(*args)

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
        user_id, device_id = None, None
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
        request.state.title = modules.get(request.url.path.strip("/").split("/", 1)[0], {}).get('name', "")

        response = await call_next(request)
        if user_id and device_id:
            await redis.set_token(user_id, device_id, response)

        return response

    error_handlers(app)

    return app
