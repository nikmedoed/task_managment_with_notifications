from datetime import datetime
from functools import reduce

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from shared.db import *
from telegram_bot.utils.keyboards import *
from telegram_bot.utils.message_magic import edit_or_resend_message, send_autodelete_message
from telegram_bot.utils.notifications import send_notify

router = Router()

DATE_FORMATS = [
    "%d %m",  # дд мм
    "%d.%m",  # дд.мм
    "%d.%m.%y",  # дд.мм.гг
    "%d.%m.%Y",  # дд.мм.гггг
    "%d%m",  # ддмм
    "%d-%m",  # дд-мм
    "%d-%m-%y",  # дд-мм-гг
    "%d-%m-%Y",  # дд-мм-гггг
    "%d%m%y",  # ддммгг
    "%d%m%Y",  # ддммгггг
]

replace_dict = {"%d": "дд", "%m": "мм", "%y": "гг", "%Y": "гггг"}

DATE_FORMATS_LIST = "\n".join([reduce(lambda s, kv: s.replace(*kv), replace_dict.items(), d) for d in DATE_FORMATS])

DATE_TEXT_FORMAT = "%d.%m.%Y"


def parse_date(date_str: str) -> datetime.date:
    """
    Парсинг даты с поддержкой нескольких форматов.
    """
    year = date.today().year
    for fmt in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_str, fmt).date()
            if parsed_date.year < year:
                parsed_date = parsed_date.replace(year=year)
            return parsed_date
        except ValueError:
            continue
    raise ValueError("Неверный формат даты")


class DateChangeStates(StatesGroup):
    waiting_for_new_date = State()
    waiting_for_comment = State()


@router.callback_query(PlanDateChangeCallback.filter())
async def initiate_date_change(callback_query: CallbackQuery, callback_data: PlanDateChangeCallback,
                               user: User, state: FSMContext, db: AsyncSession):
    task: Optional[Task] = await db.get(Task, callback_data.task_id)
    if not task:
        await callback_query.answer("Задача не найдена", show_alert=True)
        return

    user_permissions = task.user_permission(user.id)
    if not user_permissions.can_change_date:
        await callback_query.answer("Вы не можете изменить дату", show_alert=True)
        return

    await state.update_data(task_id=task.id, must_comment=user_permissions.must_comment_date)
    await state.set_state(DateChangeStates.waiting_for_new_date)
    await callback_query.answer("Укажите дату")
    message = await callback_query.message.answer(
        f"Введите новую плановую дату в одном из форматов:\n{DATE_FORMATS_LIST}",
        reply_markup=cancel_keyboard)
    await state.update_data(message_id=message.message_id)


@router.message(DateChangeStates.waiting_for_new_date)
async def process_new_date(message: Message, state: FSMContext, user: User, db: AsyncSession):
    bot = message.bot
    user_data = await state.get_data()
    task_id = user_data['task_id']
    task = await get_task_by_id(task_id, db)

    message_id = user_data.get('message_id')
    msg = message.text
    await message.delete()
    try:
        new_plan_date = parse_date(msg)
    except ValueError:
        new_message_id = await edit_or_resend_message(
            bot=bot,
            chat_id=message.chat.id,
            message_id=message_id,
            text=f"Неверный формат даты.\n"
                 f"Пожалуйста, используйте один из следующих форматов:\n{DATE_FORMATS_LIST}",
            reply_markup=cancel_keyboard
        )
        await state.update_data(message_id=new_message_id)
        return

    new_date_str = new_plan_date.strftime(DATE_TEXT_FORMAT)

    if new_plan_date == task.actual_plan_date:
        new_message_id = await edit_or_resend_message(
            bot=bot,
            chat_id=message.chat.id,
            message_id=message_id,
            text=f"👀<b>Плановая дата уже установлена на {new_date_str}</b>.\n\n"
                 f"Пожалуйста, укажите другую дату.\n"
                 f"Форматы:\n{DATE_FORMATS_LIST}",
            reply_markup=cancel_keyboard
        )
        await state.update_data(message_id=new_message_id)
        return

    if new_plan_date < datetime.now().date():
        new_message_id = await edit_or_resend_message(
            bot=bot,
            chat_id=message.chat.id,
            message_id=message_id,
            text=f"⏮<b>Плановая дата не может быть в прошлом</b>.\n\n"
                 f"{new_date_str} не подходит\n\n"
                 f"Пожалуйста, укажите дату не ранее сегодняшнего дня.\n"
                 f"Форматы:\n{DATE_FORMATS_LIST}",
            reply_markup=cancel_keyboard
        )
        await state.update_data(message_id=new_message_id)
        return

    if user_data.get('must_comment', False):
        await state.update_data(new_plan_date=new_date_str)
        await state.set_state(DateChangeStates.waiting_for_comment)
        new_message_id = await edit_or_resend_message(
            bot=bot,
            chat_id=message.chat.id,
            message_id=message_id,
            text=f"Чтобы установить дату: {new_date_str}\nпришлите причину переноса.",
            reply_markup=cancel_keyboard
        )
        await state.update_data(message_id=new_message_id)
    else:
        await finalize_date_change(task, user, new_plan_date, None, state, message, db, bot)


CALLBACK_DATE_CHANGE_NAME = "submit_date_reason"


@router.message(DateChangeStates.waiting_for_comment)
async def receive_comment(message: Message, state: FSMContext):
    user_data = await state.get_data()
    new_plan_date = user_data['new_plan_date']
    comment = message.text
    await state.update_data(comment=comment)
    await message.delete()

    new_message_id = await edit_or_resend_message(
        bot=message.bot,
        chat_id=message.chat.id,
        message_id=user_data.get('message_id'),
        text=f"Новая дата:\n{new_plan_date}\n\nПричина:\n<pre>{comment}</pre>\n\n"
             "Отправить или отменить? Можно прислать новую.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отправить", callback_data=CALLBACK_DATE_CHANGE_NAME)],
                [cancel_button]
            ]
        )
    )
    await state.update_data(message_id=new_message_id)


@router.callback_query(F.data == CALLBACK_DATE_CHANGE_NAME, DateChangeStates.waiting_for_comment)
async def submit_comment(callback_query: CallbackQuery, state: FSMContext, db: AsyncSession, user: User):
    user_data = await state.get_data()
    task_id = user_data['task_id']
    comment = user_data['comment']
    new_plan_date = datetime.strptime(user_data['new_plan_date'], DATE_TEXT_FORMAT).date()

    task = await get_task_by_id(task_id, db)
    if not task:
        await callback_query.answer("Задача не найдена", show_alert=True)
        await state.clear()
        return
    await callback_query.answer("Дата принята")
    await finalize_date_change(task, user, new_plan_date,
                               comment, state, callback_query.message, db,
                               callback_query.bot)


async def finalize_date_change(task: Task, user: User, new_plan_date: datetime.date,
                               comment: str | None,
                               state: FSMContext,
                               message: Message, db: AsyncSession, bot: Bot):
    old_plan_date = task.actual_plan_date
    await date_change(task, user, new_plan_date, comment, db=db)
    await send_notify(task, db, bot,
                      event_msg=f"Смена плановой даты задачи на\n{task.formatted_plan_date}",
                      may_edit=True)
    user_data = await state.get_data()
    message_id = user_data.get('message_id')
    await state.clear()
    await send_autodelete_message(
        f"Плановая дата задачи /{task.id} изменена\n"
        f"{old_plan_date.strftime(DATE_TEXT_FORMAT)} → {new_plan_date.strftime(DATE_TEXT_FORMAT)}.",
        chat_id=user.telegram_id,
        message=message
    )
    if message_id:
        await bot.delete_message(chat_id=user.telegram_id, message_id=message_id)
