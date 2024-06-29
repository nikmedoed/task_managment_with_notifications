from ._base import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from typing import List, TYPE_CHECKING
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from .task_types import TaskType
    from .statuses import Status
    from .objects import Object
    from .users import User
    from .comments import Comment
    from .documents import Document
    from .task_notifications import TaskNotification


class Task(BaseModel):
    __tablename__ = 'tasks'

    name: str = Column(String(100), nullable=False)
    task_type_id: int = Column(Integer, ForeignKey('task_types.id'), nullable=False)
    status_id: int = Column(Integer, ForeignKey('statuses.id'), nullable=False)
    object_id: int = Column(Integer, ForeignKey('objects.id'), nullable=False)
    supplier_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    supervisor_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    executor_id: int = Column(Integer, ForeignKey('users.id'), nullable=True)
    initial_date: DateTime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actual_date: DateTime = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    description: str = Column(Text, nullable=True)
    revision_count: int = Column(Integer, default=0, nullable=False)
    reschedule_count: int = Column(Integer, default=0, nullable=False)
    notification_count: int = Column(Integer, default=0, nullable=False)

    task_type: 'TaskType' = relationship('TaskType')
    status: 'Status' = relationship('Status')
    object: 'Object' = relationship('Object', back_populates='tasks')
    supplier: 'User' = relationship('User', foreign_keys='Task.supplier_id', back_populates='tasks_as_supplier')
    supervisor: 'User' = relationship('User', foreign_keys='Task.supervisor_id', back_populates='tasks_as_supervisor')
    executor: 'User' = relationship('User', foreign_keys='Task.executor_id', back_populates='tasks_as_executor')
    comments: List['Comment'] = relationship('Comment', back_populates='task', order_by='Comment.id')
    documents: List['Document'] = relationship('Document', secondary='task_document_comment_links', back_populates='tasks', overlaps="comments,documents")
    notifications: List['TaskNotification'] = relationship('TaskNotification', back_populates='task')
