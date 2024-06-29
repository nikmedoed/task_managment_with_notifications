from ._base import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks import Task
    from .users import User


class TaskNotification(BaseModel):
    __tablename__ = 'task_notifications'

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    task_id: int = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    telegram_message_id: int = Column(Integer, nullable=False)
    notification_type: str = Column(String(50), nullable=False)

    task: 'Task' = relationship('Task', back_populates='notifications')
    user: 'User' = relationship('User')
