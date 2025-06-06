from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from webapp.deps import templates

# Расширенный словарь сопоставления кодов ошибок с русскими описаниями и заголовками
ERROR_MESSAGES = {
    400: {
        "title": "Некорректный запрос",
        "detailed": "Запрос, который вы отправили, имеет неверный формат или содержит некорректные данные. Проверьте параметры и повторите попытку."
    },
    401: {
        "title": "Неавторизован",
        "detailed": "Вы не авторизованы для выполнения этого действия. Пожалуйста, войдите в систему и попробуйте снова."
    },
    403: {
        "title": "Доступ запрещен",
        "detailed": "У вас нет прав для доступа к этому ресурсу. Обратитесь к администратору системы, если вы считаете, что это ошибка."
    },
    404: {
        "title": "Страница не найдена",
        "detailed": "Запрашиваемая страница не существует. Проверьте URL-адрес и попробуйте снова."
    },
    405: {
        "title": "Метод не поддерживается",
        "detailed": "Метод, используемый для запроса, не поддерживается этим ресурсом. Проверьте документацию API и измените метод запроса."
    },
    409: {
        "title": "Конфликт",
        "detailed": "Запрос не может быть выполнен из-за конфликта с текущим состоянием ресурса. Повторите попытку позже или обратитесь к разработчику."
    },
    413: {
        "title": "Слишком большой запрос",
        "detailed": "Запрос, который вы отправили, слишком большой для обработки сервером."
    },
    422: {
        "title": "Ошибка валидации данных",
        "detailed": "Отправленные данные не прошли проверку. Проверьте введенные данные и повторите попытку."
    },
    500: {
        "title": "Внутренняя ошибка сервера",
        "detailed": "Произошла ошибка на сервере. Повторите попытку позже. Если проблема сохраняется, обратитесь к разработчику."
    },
    502: {
        "title": "Плохой шлюз",
        "detailed": "Сервер получил недопустимый ответ от вышестоящего сервера. Повторите попытку позже."
    },
    503: {
        "title": "Сервис недоступен",
        "detailed": "Сервер временно недоступен из-за технического обслуживания или перегрузки. Повторите попытку позже."
    },
    504: {
        "title": "Шлюз не отвечает",
        "detailed": "Сервер не получил своевременный ответ от вышестоящего сервера. Повторите попытку позже."
    }
}


def render_unactive(request: Request):
    return error_render(
        request,
        status.HTTP_403_FORBIDDEN,
        "Вас удалили",
        title="Доступ запрещен",
        extra_detail="Обратитесь к администратору системы для восстановления аккаунта"
    )


def render_unverificated(request: Request):
    return error_render(
        request,
        status.HTTP_403_FORBIDDEN,
        "Аккаунт на верификации",
        title="Верификация",
        extra_detail="Обратитесь к администратору системы для ускорения верификации"
    )


def error_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_info = ERROR_MESSAGES.get(exc.status_code, {
            "title": "Неописанная ошибка",
            "detailed": "Неописанная ошибка, обратитесь к разработчику, если повторяется"
        })
        return error_render(request,
                            exc.status_code,
                            error_info["detailed"],
                            extra_detail=str(exc.detail),
                            title=error_info["title"])

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        error_info = ERROR_MESSAGES.get(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            "title": "Ошибка валидации данных",
            "detailed": "Ошибка валидации данных, обратитесь к разработчику, если регулярно повторяется"
        })
        return error_render(request,
                            status.HTTP_422_UNPROCESSABLE_ENTITY,
                            error_info["detailed"],
                            extra_detail=str(exc.errors()),
                            title=error_info["title"])

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        error_info = ERROR_MESSAGES.get(500, {
            "title": "Внутренняя ошибка сервера",
            "detailed": "Произошла ошибка на сервере. Повторите попытку позже. Если проблема сохраняется, обратитесь к разработчику."
        })
        return error_render(request,
                            status.HTTP_500_INTERNAL_SERVER_ERROR,
                            error_info["detailed"],
                            extra_detail=str(exc),
                            title=error_info["title"])

    @app.get("/error")
    async def custom_error_handler(request: Request, status_code: int):
        error_info = ERROR_MESSAGES.get(status_code, {
            "title": "Неописанная ошибка",
            "detailed": "Неописанная ошибка, обратитесь к разработчику, если повторяется"
        })
        return error_render(request,
                            status_code,
                            error_info["detailed"],
                            title=error_info["title"])


def error_render(request: Request, code: int | str, detail: str, extra_detail: str = None, status_code: int = None,
                 title: str = None):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "status_code": code,
        "detail": detail,
        "extra_detail": extra_detail,
        "title": title or "Ошибка"
    }, status_code=status_code or code)
