import importlib
import inspect
import os
import urllib.parse

import pytz
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

import webapp.filters
from database import async_dbsession, get_db
from shared.app_config import app_config
from shared.db import get_user_by_tg
from webapp.deps import redis, BASE_DIR, templates, generate_static_template
from webapp.endpoints import auth, register, tasks
from webapp.endpoints import tasks
from webapp.errors import error_handlers, render_unactive, render_unverificated

SYSTEM_NAME = "Прайм контроль"

modules = {
    'auth': {'name': 'Авторизация'},
    'register': {'name': 'Регистрация'},
    'tasks': {'name': 'Мои задачи', 'icon': 'card-checklist', 'secured': True},
    'tasks_archive': {'name': 'Все задачи', 'icon': 'archive', 'secured': True, "only_admin": True},
    'users': {'name': 'Пользователи', 'icon': 'people', 'secured': True},
    'documents': {'name': 'Документы', 'icon': 'file-earmark-text', 'secured': True},
    'references': {'name': 'Справочники', 'icon': 'journal-bookmark', 'secured': True}
}

templates.env.globals['secured_modules'] = {k: v for k, v in modules.items() if v.get('secured')}
templates.env.globals['SYSTEM_NAME'] = SYSTEM_NAME
templates.env.globals['bot_link'] = app_config.telegram.bot_link
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

    app.mount("/static/vendor", StaticFiles(directory=os.path.join(BASE_DIR, "../webapp_theme_static/vendor")),
              name="uploads")
    app.mount("/static/css", StaticFiles(directory=os.path.join(BASE_DIR, "../webapp_theme_static/css")),
              name="uploads")
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

    @app.middleware('http')
    async def middleware(request: Request, call_next):
        user_id, device_id = None, None
        path = request.url.path
        route = 'tasks' if path == "/" else path.strip("/").split("/", 1)[0]

        module_data = modules.get(route, {})
        if module_data.get('secured'):
            url_safe_path = urllib.parse.quote(path, safe='')
            user_id, device_id = await redis.check_token(request)

            if not user_id:
                return await auth.login(request, next_path=url_safe_path)

            async with async_dbsession() as session:
                user = await get_user_by_tg(user_id, session)
            if not user:
                return await auth.login(request, next_path=url_safe_path)

            if not user.active:
                return render_unactive(request)
            if not user.verificated:
                return render_unverificated(request)

            if module_data.get('only_admin') and not user.admin:
                raise HTTPException(status_code=403, detail="У вас нет допуска для этого действия")

            request.state.user = user

        timezone = request.headers.get('X-Timezone', 'UTC')
        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            timezone = 'UTC'
        request.state.timezone = timezone

        request.state.title = module_data.get('name', "")
        response = await call_next(request)
        if user_id and device_id:
            await redis.set_token(user_id, device_id, response)

        return response

    error_handlers(app)

    return app
