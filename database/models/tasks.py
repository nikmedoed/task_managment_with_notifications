from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from ._base import BaseModel
from .statuses import (Statuses,
                       COMPLETED_STATUSES, SUPERVISOR_STATUSES,
                       EXECUTOR_STATUSES, SUPPLIER_STATUSES,
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

    name: str = Column(String(100), nullable=False)
    task_type_id: int = Column(Integer, ForeignKey('task_types.id'), nullable=False)
    status = Column(SQLAlchemyEnum(Statuses), nullable=False)
    object_id: int = Column(Integer, ForeignKey('objects.id'), nullable=False)
    supplier_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    supervisor_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    executor_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    initial_plan_date: DateTime = Column(DateTime(timezone=True), nullable=False)
    actual_plan_date: DateTime = Column(DateTime(timezone=True), nullable=False)
    last_notification_date: DateTime = Column(DateTime(timezone=True), nullable=True)
    description: str = Column(Text, nullable=False)
    rework_count: int = Column(Integer, default=0, nullable=False)
    reschedule_count: int = Column(Integer, default=0, nullable=False)
    notification_count: int = Column(Integer, default=0, nullable=False)

    task_type: 'TaskType' = relationship('TaskType')
    object: 'Object' = relationship('Object', back_populates='tasks')
    supplier: 'User' = relationship('User', foreign_keys='Task.supplier_id', back_populates='tasks_as_supplier')
    supervisor: 'User' = relationship('User', foreign_keys='Task.supervisor_id', back_populates='tasks_as_supervisor')
    executor: 'User' = relationship('User', foreign_keys='Task.executor_id', back_populates='tasks_as_executor')
    comments: List['Comment'] = relationship('Comment', back_populates='task', order_by='Comment.id')
    documents: List['Document'] = relationship('Document', secondary='task_document_comment_links',
                                               back_populates='tasks', overlaps="comments,documents")
    notifications: List['TaskNotification'] = relationship('TaskNotification', back_populates='task')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.actual_plan_date:
            self.actual_plan_date = self.initial_plan_date

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
