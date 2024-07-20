from enum import Enum

from sqlalchemy import Column, String, Boolean, Text

from ._base import BaseModel


class Status(BaseModel):
    __tablename__ = 'statuses'

    name: str = Column(String(50), nullable=False, unique=True)
    description: str = Column(Text, nullable=True)
    active: bool = Column(Boolean, nullable=False, default=True)


class Statuses(Enum):
    DRAFT = 'Черновик'
    PLANNING = 'Планирование'
    ACCEPTED = 'Принято'
    REJECTED = 'Отклонено'
    REVIEW = 'Проверка'
    CANCELED = 'Отмена'
    REWORK = 'Доработка'
    DONE = 'Выполнено'


COMPLETED_STATUSES = {Statuses.DONE, Statuses.CANCELED}
SUPPLIER_STATUSES = {Statuses.DRAFT, Statuses.PLANNING, Statuses.ACCEPTED,
                     Statuses.REJECTED, Statuses.REVIEW, Statuses.REWORK}
EXECUTOR_STATUSES = {Statuses.PLANNING, Statuses.ACCEPTED, Statuses.REWORK}
SUPERVISOR_STATUSES = {Statuses.REVIEW}

STATUS_TRANSITIONS = {
    Statuses.DRAFT: {Statuses.PLANNING},
    Statuses.PLANNING: {Statuses.ACCEPTED, Statuses.REJECTED},
    Statuses.REJECTED: {Statuses.PLANNING},
    Statuses.ACCEPTED: {Statuses.REVIEW},
    Statuses.REVIEW: {Statuses.DONE, Statuses.REWORK},
    Statuses.REWORK: {Statuses.REVIEW},
    Statuses.DONE: {Statuses.REWORK},
}


def is_valid_transition(current_status, new_status):
    if new_status == Statuses.CANCELED or current_status == Statuses.CANCELED:
        return True
    return new_status in STATUS_TRANSITIONS.get(current_status, set())
