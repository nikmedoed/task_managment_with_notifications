from aiogram.types import Message

from database.models import Task, User, CommentType, Statuses
from shared.app_config import app_config


async def send_task(message: Message, task: Task, user: User, event: str = "Пример"):
    task_info = (
        f"<b>№ п/п:</b> {task.id}{' ❗️<b>важная</b>' if task.important else ''}\n"
        f"<b>Создано:</b> {task.time_created.strftime('%d.%m.%Y')}\n"
        f"<b>Обновлено:</b> {task.time_updated.strftime('%d.%m.%Y')}\n"
        f"<b>Объект:</b> {task.object.name}\n"
        f"<b>Тип:</b> <a href='{app_config.domain}/tasks/{task.id}'>{task.task_type.name}</a>\n"
        f"<b>Срок:</b> {task.formatted_plan_date}\n"
        f"<b>Статус:</b> {task.status.value}\n"
        f"<b>Описание:</b>\n {task.description}\n"
        f"\n"
        f"<b>Постановщик:</b> <a href='{task.supplier.telegram_bot_link}'>{task.supplier.full_name}</a>\n"
        f"<b>Руководитель:</b> <a href='{task.supervisor.telegram_bot_link}'>{task.supervisor.full_name}</a>\n"
        f"<b>Исполнитель:</b> <a href='{task.executor.telegram_bot_link}'>{task.executor.full_name}</a>\n"
    )
    if event:
        task_info = f"<b>{event}</b>\n\n{task_info}"

    if task.comments:
        comments = []
        has_comment = False
        for comment in task.comments:
            has_comment = has_comment or comment.type == CommentType.comment
            roles = ', '.join([role[0] for role in comment.author_roles])
            comment_info = [f"<b>{comment.time_updated.strftime('%d.%m.%y %H:%M')}</b>"]
            if comment.user:
                comment_info.append(f"<b>{comment.user.short_name}</b>")
            if roles:
                comment_info.append(f"({roles})")
            comment_info = " ".join(comment_info)

            if comment.type == CommentType.status_change:
                comment_info += (
                    f"\n🔁 Статус \"{Statuses[comment.previous_status].value}\" → "
                    f"\"{Statuses[comment.new_status].value}\""
                )
            elif comment.type == CommentType.date_change:
                diff_days = (comment.new_date - comment.old_date).days
                comment_info += (
                    f"\n🗓 Срок до \"{comment.old_date.strftime('%d.%m.%Y')}\" → "
                    f"\"{comment.new_date.strftime('%d.%m.%Y')}\" "
                    f"({f'+{diff_days}' if diff_days > 0 else diff_days} дн.)"
                )
            elif comment.type == CommentType.user_change:
                comment_info += (
                    f"\n💁‍♂️ {'Исполнитель' if comment.extra_data['role'] == 'executor' else 'Руководитель'} "
                    f"\"{comment.extra_data['old_user']['name']}\" → "
                    f"\"{comment.extra_data['new_user']['name']}\""
                )
            if comment.content:
                if comment.type == CommentType.error:
                    comment_info += f"\n⚠️ <i>{comment.content.strip()}</i>"
                else:
                    comment_info += (f"\n{'💬 ' if comment.type == CommentType.comment else ""}"
                                     f"{comment.content.strip()}")

            if comment.documents:
                documents_info = "\n".join(
                    f"- {doc.title}" if doc.deleted else f"- <a href='{app_config.domain}/documents/{doc.uuid}'>{doc.title}</a>"
                    for doc in comment.documents
                )
                comment_info += f"\n{documents_info}"

            comments.append(comment_info)

            if len(comments) >= 5 and has_comment:
                break

        task_info = f"{task_info}\n\n<b>Последние комментарии</b>\n\n{'\n\n'.join(comments)}"

    await message.answer(
        task_info,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
