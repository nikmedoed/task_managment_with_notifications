import os

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from shared.app_config import app_config
from .utils.RedisStore import RedisTokenManager

redis = RedisTokenManager(**app_config.redis.dict(), jwt_secret_key=app_config.telegram.jwt_secret_key)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

STATIC_DIR = os.path.join(BASE_DIR, "templates/static")
os.makedirs(STATIC_DIR, exist_ok=True)


def generate_static_template(template_name: str, context: dict, output_name: str):
    context["request"] = Request({
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "query_string": b"",
        "headers": [],
    })

    content = templates.TemplateResponse(template_name, context).body.decode('utf-8')
    with open(os.path.join(STATIC_DIR, output_name), "w", encoding='utf-8') as f:
        f.write(content)
