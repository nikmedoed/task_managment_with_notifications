from ._base import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks import Task
    from .users import User


class TaskNotification(BaseModel):
    __tablename__ = 'task_notifications'

    task_id: int = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    telegram_message_id: int = Column(Integer, nullable=False)

    task: 'Task' = relationship('Task', back_populates='notifications')
    user: 'User' = relationship('User')
