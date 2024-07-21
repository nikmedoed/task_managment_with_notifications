import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from ._base import BaseModel

if TYPE_CHECKING:
    from .comments import Comment
    from .users import User
    from .power_of_attorneys import PowerOfAttorney


class Document(BaseModel):
    __tablename__ = 'documents'

    uuid: str = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    title: str = Column(String(200), nullable=False)
    type: str = Column(String(100), nullable=False)
    author_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    comment_id: int = Column(Integer, ForeignKey('comments.id'), nullable=False)
    power_of_attorney_id: int = Column(Integer, ForeignKey('power_of_attorneys.id'), nullable=True)

    author: 'User' = relationship('User', back_populates='documents')
    comment: 'Comment' = relationship('Comment', back_populates='documents')
    power_of_attorney: 'PowerOfAttorney' = relationship('PowerOfAttorney', back_populates='documents')
