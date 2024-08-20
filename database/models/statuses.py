from enum import Enum

from sqlalchemy import Column, String, Boolean, Text

from . import UserRole
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
    REJECTED = 'Отказ'
    REVIEW = 'Проверка'
    CANCELED = 'Отмена'
    REWORK = 'Доработка'
    DONE = 'Выполнено'


COMPLETED_STATUSES = {Statuses.DONE, Statuses.CANCELED}
NOTIFICATION_STATUSES = set(Statuses) - COMPLETED_STATUSES - {Statuses.DRAFT}

SUPPLIER_STATUSES = {Statuses.DRAFT, Statuses.PLANNING, Statuses.ACCEPTED,
                     Statuses.REJECTED}
EXECUTOR_STATUSES = {Statuses.PLANNING, Statuses.ACCEPTED, Statuses.REWORK}
SUPERVISOR_STATUSES = {Statuses.REVIEW}

SHOULD_BE_COMMENTED = {Statuses.REWORK, Statuses.REJECTED}

ROLE_STATUS_TRANSITIONS = {
    UserRole.SUPPLIER: {
        Statuses.DRAFT: {Statuses.PLANNING},
        Statuses.CANCELED: {Statuses.PLANNING},
        Statuses.REJECTED: {Statuses.PLANNING},
        Statuses.DONE: {Statuses.REWORK},
        Statuses.PLANNING: {Statuses.DRAFT}
    },
    UserRole.EXECUTOR: {
        Statuses.PLANNING: {Statuses.ACCEPTED, Statuses.REVIEW, Statuses.REJECTED},
        Statuses.ACCEPTED: {Statuses.REVIEW, Statuses.REJECTED},
        Statuses.REJECTED: {Statuses.ACCEPTED},
        Statuses.REWORK: {Statuses.REJECTED, Statuses.REVIEW},
    },
    UserRole.SUPERVISOR: {
        Statuses.REVIEW: {Statuses.DONE, Statuses.REWORK},
    }
}


def is_valid_transition(current_status, new_status, user_roles: set):
    if new_status == Statuses.CANCELED or current_status == Statuses.CANCELED:
        return UserRole.SUPPLIER in user_roles
    return any(new_status in ROLE_STATUS_TRANSITIONS.get(role, {}).get(current_status, set()) for role in user_roles)
