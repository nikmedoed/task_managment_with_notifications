from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup

from database.models import User, Task


class StatusChangeCallback(CallbackData, prefix="status_change"):
    task_id: int
    status: str


class AcknowledgeCallback(CallbackData, prefix="ack"):
    task_id: int


class PlanDateChangeCallback(CallbackData, prefix="plan_date_change"):
    task_id: int


cancel_callback_data = "cancel_commenting"
cancel_button = InlineKeyboardButton(text="Отмена", callback_data=cancel_callback_data)
cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])


def generate_status_keyboard(user: User, task: Task):
    user_permissions = task.user_permission(user.id)
    keyboard = InlineKeyboardBuilder()

    if user_permissions.can_change_date:
        keyboard.row(
            InlineKeyboardButton(
                text="🗓 Изменить плановую дату 🗓",
                callback_data=PlanDateChangeCallback(task_id=task.id).pack()
            )
        )

    if user_permissions.available_statuses:
        buttons = [
            InlineKeyboardButton(
                text=f"{status.value}",
                callback_data=StatusChangeCallback(task_id=task.id, status=status.name).pack()
            ) for status in user_permissions.available_statuses
        ]
        for i in range(0, len(buttons), 2):
            keyboard.row(*buttons[i:i + 2])
    else:
        keyboard.row(
            InlineKeyboardButton(
                text="Ознакомлен, скрыть",
                callback_data=AcknowledgeCallback(task_id=task.id).pack()
            )
        )

    return keyboard.as_markup()
