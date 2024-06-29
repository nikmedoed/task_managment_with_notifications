import uuid
from ._base import BaseModel
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks import Task
    from .comments import Comment
    from .users import User
    from .power_of_attorneys import PowerOfAttorney


class Document(BaseModel):
    __tablename__ = 'documents'

    uuid: str = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    title: str = Column(String(200), nullable=False)
    type: str = Column(String(100), nullable=False)
    author_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)

    author: 'User' = relationship('User', back_populates='documents')
    tasks: List['Task'] = relationship('Task', secondary='task_document_comment_links', back_populates='documents',
                                       overlaps="comments")
    comments: List['Comment'] = relationship('Comment', secondary='task_document_comment_links',
                                             back_populates='documents', overlaps="tasks")
    power_of_attorneys: List['PowerOfAttorney'] = relationship('PowerOfAttorney', back_populates='document')
