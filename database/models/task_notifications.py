from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ._base import BaseModel

if TYPE_CHECKING:
    from .tasks import Task
    from .users import User


class TaskNotification(BaseModel):
    __tablename__ = 'task_notifications'

    task_id: int = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    telegram_message_id: int = Column(Integer, nullable=False)
    active: bool = Column(Boolean, nullable=False, default=True)

    task: 'Task' = relationship('Task', back_populates='notifications')
    user: 'User' = relationship('User')
