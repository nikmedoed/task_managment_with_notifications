from datetime import datetime
from typing import List, TYPE_CHECKING

import pytz
from sqlalchemy import (Column, Integer, ForeignKey, DateTime, Text,
                        Enum as SQLAlchemyEnum, select, Boolean)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, aliased

from ._base import BaseModel
from ._user_roles import UserRole
from .statuses import (Statuses, COMPLETED_STATUSES, SUPERVISOR_STATUSES, EXECUTOR_STATUSES, SUPPLIER_STATUSES,
                       is_valid_transition)

if TYPE_CHECKING:
    from .task_types import TaskType
    from .objects import Object
    from .users import User
    from .comments import Comment
    from .documents import Document
    from .task_notifications import TaskNotification


class Task(BaseModel):
    __tablename__ = 'tasks'

    task_type_id: int = Column(Integer, ForeignKey('task_types.id'), nullable=False)
    status = Column(SQLAlchemyEnum(Statuses), nullable=False)
    object_id: int = Column(Integer, ForeignKey('objects.id'), nullable=False)
    supplier_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    supervisor_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    executor_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    initial_plan_date: datetime = Column(DateTime(timezone=True), nullable=False)
    actual_plan_date: datetime = Column(DateTime(timezone=True), nullable=False)
    last_notification_date: datetime = Column(DateTime(timezone=True), nullable=True)
    description: str = Column(Text, nullable=False)
    rework_count: int = Column(Integer, default=0, nullable=False)
    reschedule_count: int = Column(Integer, default=0, nullable=False)
    notification_count: int = Column(Integer, default=0, nullable=False)
    important: bool = Column(Boolean, nullable=False, default=False)

    task_type: 'TaskType' = relationship('TaskType')
    object: 'Object' = relationship('Object', back_populates='tasks')

    supplier: 'User' = relationship('User', foreign_keys='Task.supplier_id',
                                    back_populates='tasks_as_supplier', lazy='joined')
    supervisor: 'User' = relationship('User', foreign_keys='Task.supervisor_id',
                                      back_populates='tasks_as_supervisor', lazy='joined')
    executor: 'User' = relationship('User', foreign_keys='Task.executor_id',
                                    back_populates='tasks_as_executor', lazy='joined')
    comments: List['Comment'] = relationship('Comment', back_populates='task',
                                             order_by='Comment.id')
    notifications: List['TaskNotification'] = relationship('TaskNotification',
                                                           back_populates='task')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.actual_plan_date:
            self.actual_plan_date = self.initial_plan_date

    @hybrid_property
    def plan_date_shift(self):
        if self.actual_plan_date and self.initial_plan_date:
            return (self.actual_plan_date - self.initial_plan_date).days
        return 0

    @hybrid_property
    def days_remain(self):
        if self.actual_plan_date:
            delta = self.actual_plan_date.astimezone(pytz.UTC) - datetime.now(pytz.UTC)
            return delta.days
        return None

    @hybrid_property
    def is_active(self):
        return self.status not in COMPLETED_STATUSES

    @classmethod
    def filter_completed(cls):
        return cls.status.in_(COMPLETED_STATUSES)

    @classmethod
    def filter_for_supplier(cls):
        return cls.status.in_(SUPPLIER_STATUSES)

    @classmethod
    def filter_for_executor(cls):
        return cls.status.in_(EXECUTOR_STATUSES)

    @classmethod
    def filter_for_supervisor(cls):
        return cls.status.in_(SUPERVISOR_STATUSES)

    def update_status(self, new_status: Statuses):
        if is_valid_transition(self.status, new_status):
            self.status = new_status
        else:
            raise ValueError(f"Недопустим перевод из статуса '{self.status}' в '{new_status}'")

    async def set_cancel_if_not(self, session: AsyncSession):
        if self.status != Statuses.CANCELED:
            self.update_status(Statuses.CANCELED)
            await session.commit()

    @hybrid_property
    def documents(self):
        documents = []
        for comment in self.comments:
            documents.extend(comment.documents)
        return documents

    @documents.expression
    def documents(cls):
        from .documents import Document
        from .comments import Comment
        DocumentAlias = aliased(Document)
        return (
            select(DocumentAlias)
            .select_from(Comment)
            .join(DocumentAlias, Comment.id == DocumentAlias.comment_id)
            .where(Comment.task_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    def get_user_roles(self, user_id: int):
        roles = set()
        if user_id == self.supplier_id:
            roles.add(UserRole.SUPPLIER)
        if user_id == self.executor_id:
            roles.add(UserRole.EXECUTOR)
        if user_id == self.supervisor_id:
            roles.add(UserRole.SUPERVISOR)
        if not roles:
            roles.add(UserRole.GUEST)
        return roles

    @property
    def formatted_plan_date(self) -> str:
        if self.actual_plan_date == self.initial_plan_date:
            return self.actual_plan_date.strftime('%d.%m.%Y')
        else:
            plan_date_shift = (self.actual_plan_date - self.initial_plan_date).days
            return (
                f"{self.actual_plan_date.strftime('%d.%m.%Y')} "
                f"(план {self.initial_plan_date.strftime('%d.%m.%Y')} "
                f"{plan_date_shift:+}д.)"
            )
