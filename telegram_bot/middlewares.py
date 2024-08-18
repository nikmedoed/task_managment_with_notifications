from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database import async_dbsession
from shared.app_config import app_config
from shared.db import get_user_by_tg


class UserCheckMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            # Проверяем тип события, чтобы получить telegram_id
            if event.message:
                telegram_id = event.message.from_user.id
            elif event.callback_query:
                telegram_id = event.callback_query.from_user.id
            elif event.inline_query:
                telegram_id = event.inline_query.from_user.id
            else:
                return await handler(event, data)
        else:
            return await handler(event, data)
        async with async_dbsession() as session:
            user = await get_user_by_tg(telegram_id, session)
        if not user:
            return await event.answer(
                f"Ваш аккаунт не связан с пользователем <a href='{app_config.domain}/tasks'>нашей системы</a>."
                "Зарегистрируйтесь и дождитесь верификации администратором"
            )
        if not user.active:
            return await event.answer(
                "Ваш аккаунт деактивирован. Обратитесь к администратору."
            )
        if not user.verificated:
            return await event.answer(
                "Ваш аккаунт на верификации. Обратитесь к администратору для ускорения."
            )
        data["user"] = user
        return await handler(event, data)
