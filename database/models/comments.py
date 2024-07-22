import enum
from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer, Text, ForeignKey, JSON, DateTime, String, Enum
from sqlalchemy.orm import relationship, Mapped

from ._base import BaseModel

if TYPE_CHECKING:
    from .tasks import Task
    from .documents import Document
    from .users import User


class UserRole(str, enum.Enum):
    SUPPLIER = "Постановщик"
    EXECUTOR = "Исполнитель"
    SUPERVISOR = "Руководитель"
    GUEST = 'Гость'


class CommentType(enum.Enum):
    error = "error"
    comment = "comment"
    status_change = "status_change"
    date_change = "date_change"
    user_change = "user_change"


class Comment(BaseModel):
    __tablename__ = 'comments'

    type: Mapped[CommentType] = Column(Enum(CommentType), nullable=False)
    task_id: Mapped[int] = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=True)
    author_role: Mapped[UserRole] = Column(Enum(UserRole), nullable=True)
    content: Mapped[str] = Column(Text, nullable=True)
    extra_data: Mapped[dict] = Column(JSON, nullable=True)
    previous_status: Mapped[str] = Column(String(50), nullable=True)
    new_status: Mapped[str] = Column(String(50), nullable=True)
    old_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)
    new_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)

    task: Mapped['Task'] = relationship('Task', back_populates='comments')
    user: Mapped['User'] = relationship('User', back_populates='comments')
    documents: Mapped[List['Document']] = relationship('Document', back_populates='comment')
