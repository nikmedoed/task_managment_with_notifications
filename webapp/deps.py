import os
from starlette.templating import Jinja2Templates
from database import async_dbsession
from sqlalchemy.ext.asyncio import AsyncSession
from shared.app_config import app_config
from starlette.responses import Response
# from joserfc import jwt
# from joserfc.errors import JoseError
# from fastapi import Request
from .utils.RedisStore import RedisTokenManager

# from webapp.utils.RedisStore import COOKIE_AUTH, REDIS_TTL

redis = RedisTokenManager(app_config.redis.create_connector(RedisTokenManager),
                          jwt_secret_key=app_config.telegram.jwt_secret_key)

#
# async def set_token(user_id, device_id, response=None):
#     token = jwt.encode({'alg': 'HS256'}, {'k': user_id, 'd': device_id}, app_config.telegram.jwt_secret_key)
#     await redis.set(f"{COOKIE_AUTH}:{user_id}:{device_id}", token, ex=REDIS_TTL)
#     if response:
#         response.set_cookie(key=COOKIE_AUTH, value=token, max_age=REDIS_TTL)
#     return token


# async def check_token(token: [str | Request]):
#     if isinstance(token, Request):
#         token = token.cookies.get(COOKIE_AUTH)
#     if not token:
#         return None, None
#     try:
#         token_parts = jwt.decode(token, app_config.telegram.jwt_secret_key)
#     except JoseError:
#         return None, None
#     user_id = token_parts.claims['k']
#     device_id = token_parts.claims['d']
#     stored_token = await redis.get(f"{COOKIE_AUTH}:{user_id}:{device_id}")
#     if not stored_token or stored_token.decode('utf-8') != token:
#         return None, None
#
#     return user_id, device_id


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_NAME = "Прайм контроль"
titles = {
    "/auth": "Авторизация",
    "/users": "Пользователи",
    "/tasks": "Задачи",
    "/register": "Регистрация",
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


REDIS_KEY_USER_REGISTER = "user_register"
