from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Task
from shared.db import add_comment
from telegram_bot.utils.keyboards import cancel_callback_data, AcknowledgeCallback

router = Router()


@router.callback_query(F.data == cancel_callback_data)
async def cancel_comment(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await callback_query.answer("Действие отменено")
    await state.clear()


@router.callback_query(AcknowledgeCallback.filter())
async def handle_acknowledge(call: CallbackQuery, callback_data: AcknowledgeCallback, user: User, db: AsyncSession):
    task: Optional[Task] = await db.get(Task, callback_data.task_id)
    if not task:
        await call.answer("Задача более недоступна в базе", show_alert=True)
        return
    await add_comment(task, user, db=db)
    await call.message.delete()
    await call.answer("Записано")
