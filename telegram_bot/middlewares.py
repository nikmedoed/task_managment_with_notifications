from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from aiogram.types import TelegramObject, Update, Message, CallbackQuery, InlineQuery

from database import async_dbsession
from shared.db import get_user_by_tg


class UserAndDBSessionCheckMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        telegram_id = None
        username = None
        if isinstance(event, Update):
            if event.message:
                telegram_id = event.message.from_user.id
                username = event.message.from_user.username
            elif event.callback_query:
                telegram_id = event.callback_query.from_user.id
                username = event.callback_query.from_user.username
            elif event.inline_query:
                telegram_id = event.inline_query.from_user.id
                username = event.inline_query.from_user.username

        if not telegram_id:
            return await handler(event, data)

        async with async_dbsession() as session:
            user = await get_user_by_tg(telegram_id, session)
            if not user:
                await self._send_response(
                    event,
                    "Ваш аккаунт не связан с пользователем "
                    "<a href='{app_config.domain}'>нашей системы</a>. "
                    "Зарегистрируйтесь и дождитесь верификации администратором")
                return
            if not user.active:
                await self._send_response(
                    event, "Ваш аккаунт деактивирован. "
                           "Обратитесь к администратору.")
                return
            if not user.verificated:
                await self._send_response(
                    event,
                    "Ваш аккаунт на верификации. "
                    "Обратитесь к администратору для ускорения.")
                return

            if user.nickname != username:
                user.nickname = username
                await session.commit()

            data['db'] = session
            data["user"] = user
            return await handler(event, data)

    @staticmethod
    async def _send_response(self, event: TelegramObject, message: str):
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
        elif isinstance(event, InlineQuery):
            result = InlineQueryResultArticle(
                id="1",
                title="Ответ",
                input_message_content=InputTextMessageContent(message_text=message)
            )
            await event.answer(results=[result], cache_time=0)
