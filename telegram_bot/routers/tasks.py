from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import async_dbsession
from database.models import UserRole, User
from shared.app_config import app_config
from shared.db import get_user_tasks, get_task_by_id
from telegram_bot.utils.send_tasks import send_task

router = Router()

commands = {
    'tasks': "Получить мои задач"
}

DESCRIPTION_TRIM_SIZE = 65
MESSAGE_MAX_LENGTH = 4096


def split_message_by_limit(blocks: list[str]) -> list[str]:
    start_idx = 0
    current_length = 0
    messages = []
    for i, part in enumerate(blocks):
        part_length = len(part) + 1
        if current_length + part_length > MESSAGE_MAX_LENGTH:
            messages.append("\n".join(blocks[start_idx:i]))
            start_idx = i
            current_length = 0
        current_length += part_length

    if start_idx < len(blocks):
        messages.append("\n".join(blocks[start_idx:]))

    return messages


@router.message(Command(commands=["tasks"]))
async def list_tasks(message: Message, user: User):
    async with async_dbsession() as db:
        tasks = await get_user_tasks(user.id, db)

    result = [f"<a href='{app_config.domain}/tasks'>Активные задачи пользователя</a>\n{user.full_name}"]

    for role in UserRole:
        task_list = tasks.get(f"{role.name.lower()}_tasks", [])
        if task_list:
            result.append(f"\n\n<b>{str(role)}</b>")
            max_id_len = len(str(max(task.id for task in task_list)))
            for task in task_list:
                description = task.description[:DESCRIPTION_TRIM_SIZE]
                if len(task.description) > DESCRIPTION_TRIM_SIZE:
                    if " " in description:
                        description = description[:description.rfind(" ")] + "…"
                    else:
                        description = description + "…"

                task_info = (f"\n/{task.id:0{max_id_len}d} {task.actual_plan_date.strftime('%d.%m.%y')} :: "
                             f"<a href='{app_config.domain}/tasks/{task.id}'>{task.task_type.name}</a>\n"
                             f"{description}")
                result.append(task_info)

    messages = split_message_by_limit(result)
    for mes in messages:
        await message.answer(mes, parse_mode="HTML")


@router.message(lambda message: message.text and message.text.lstrip('/').isdigit())
async def handle_task_by_id(message: Message, user: User):
    task_id = int(message.text.lstrip('/'))
    async with async_dbsession() as db:
        task = await get_task_by_id(task_id, db)
        if not task:
            return await message.reply("Задача не найдена.")

    await send_task(message, task, user)


