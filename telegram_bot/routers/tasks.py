from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserRole, User
from shared.app_config import app_config
from shared.db import get_user_tasks, get_task_by_id
from telegram_bot.utils.send_tasks import send_new_task_message, get_telegram_task_text
from telegram_bot.utils.split_by_limit import split_message_by_limit

router = Router()

commands = {
    'tasks': "Получить мои задач"
}

DESCRIPTION_TRIM_SIZE = 65


@router.message(Command(commands=["tasks"]))
async def list_tasks(message: Message, user: User, db: AsyncSession):
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
        await message.answer(mes)


@router.message(lambda message: message.text and message.text.lstrip('/').isdigit())
async def handle_task_by_id(message: Message, db: AsyncSession, user: User):
    task_id = int(message.text.lstrip('/'))
    task = await get_task_by_id(task_id, db)
    if not task:
        return await message.reply("Задача не найдена.")
    task_info = get_telegram_task_text(task)

    await send_new_task_message(task_info, task, user, message=message, db=db)
