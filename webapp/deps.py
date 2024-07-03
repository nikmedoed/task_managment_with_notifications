import os
from fastapi import Request
from starlette.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from database import async_dbsession
from sqlalchemy.ext.asyncio import AsyncSession
from shared.app_config import app_config
from starlette.responses import Response

COOKIE_NAME = 'auth-token'
redis = app_config.redis.create_connector()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_NAME = "Прайм контроль"
titles = {
    "/auth": "Авторизация",
    "/register": "Авторизация",
    "/users": "Пользователи",
    "/tasks": "Задачи",
}

for route, title in titles.items():
    titles[route] = f"{title} – {SYSTEM_NAME}"


class CustomTemplateResponse(Response):
    media_type = "text/html"

    def __init__(self, template_name: str, context: dict, *args, **kwargs):
        request = context.get("request")
        if request:
            context["title"] = context.get("title") or self.get_title(request.url.path)
        template = templates.get_template(template_name)
        content = template.render(context)
        super().__init__(content, *args, **kwargs)

    def get_title(self, path: str) -> str:
        for route, title in titles.items():
            if path.startswith(route):
                return title
        return SYSTEM_NAME


class CustomJinja2Templates(Jinja2Templates):
    def TemplateResponse(self, name: str, context: dict, *args, **kwargs):
        return CustomTemplateResponse(name, context, *args, **kwargs)


templates = CustomJinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


async def get_db() -> AsyncSession:
    async with async_dbsession() as session:
        yield session
