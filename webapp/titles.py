from webapp.deps import templates

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


templates.env.globals['get_title'] = get_title
templates.env.globals['SYSTEM_NAME'] = SYSTEM_NAME
