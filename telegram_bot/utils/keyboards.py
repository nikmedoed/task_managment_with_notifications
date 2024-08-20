from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import User, Task


class StatusChangeCallback(CallbackData, prefix="status_change"):
    task_id: int
    status: str


class AcknowledgeCallback(CallbackData, prefix="ack"):
    task_id: int


def generate_status_keyboard(user: User, task: Task):
    available_statuses = task.get_available_statuses_for_user(user.id)
    keyboard = InlineKeyboardBuilder()

    if available_statuses:
        for status in available_statuses:
            keyboard.add(
                InlineKeyboardButton(
                    text=f"{status.value}",
                    callback_data=StatusChangeCallback(task_id=task.id, status=status.name).pack()
                )
            )
    else:
        keyboard.add(
            InlineKeyboardButton(
                text="Ознакомлен, скрыть",
                callback_data=AcknowledgeCallback(task_id=task.id).pack()
            )
        )
    keyboard.adjust(2)
    return keyboard.as_markup()
