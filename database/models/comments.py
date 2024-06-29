from ._base import BaseModel
from sqlalchemy import Table, Column, Integer, Text, ForeignKey, JSON, DateTime, String, Enum
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING
import enum

if TYPE_CHECKING:
    from .tasks import Task
    from .documents import Document
    from .users import User


class CommentType(enum.Enum):
    error = "error"
    comment = "comment"
    status_change = "status_change"


class Comment(BaseModel):
    __tablename__ = 'comments'

    type: Mapped[CommentType] = Column(Enum(CommentType), nullable=False)
    task_id: Mapped[int] = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=True)
    author_role: Mapped[str] = Column(String(50), nullable=True)
    content: Mapped[str] = Column(Text, nullable=True)
    extra_data: Mapped[dict] = Column(JSON, nullable=True)
    previous_status: Mapped[str] = Column(String(50), nullable=True)
    new_status: Mapped[str] = Column(String(50), nullable=True)
    old_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)
    new_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)

    task: Mapped['Task'] = relationship('Task', back_populates='comments')
    user: Mapped['User'] = relationship('User', back_populates='comments')
    documents: Mapped[List['Document']] = relationship('Document', secondary='task_document_comment_links', back_populates='comments', overlaps="tasks,documents")


task_document_comment_links = Table(
    'task_document_comment_links', BaseModel.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True),
    Column('document_id', Integer, ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
    Column('comment_id', Integer, ForeignKey('comments.id', ondelete='CASCADE'), primary_key=True)
)
