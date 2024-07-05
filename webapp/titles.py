from starlette.responses import Response
from starlette.templating import Jinja2Templates

from webapp import templates

SYSTEM_NAME = "Прайм контроль"

titles = {
    "/auth": "Авторизация",
    "/users": "Пользователи",
    "/tasks": "Задачи",
    "/register": "Регистрация",
}

for route, title in titles.items():
    titles[route] = f"{title} – {SYSTEM_NAME}"


def get_title(path: str) -> str:
    for route, title in titles.items():
        if path.startswith(route):
            return title
    return SYSTEM_NAME

class CustomTemplateResponse(Response):
    media_type = "text/html"

    def __init__(self, template_name: str, context: dict, *args, **kwargs):
        request = context.get("request")
        if request:
            context["title"] = context.get("title") or get_title(request.url.path)
        template = templates.get_template(template_name)
        content = template.render(context)
        super().__init__(content, *args, **kwargs)


class CustomJinja2Templates(Jinja2Templates):
    def TemplateResponse(self, name: str, context: dict, *args, **kwargs):
        return CustomTemplateResponse(name, context, *args, **kwargs)
