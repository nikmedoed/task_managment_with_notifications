import enum
from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer, Text, ForeignKey, JSON, DateTime, String, Enum
from sqlalchemy.orm import relationship, Mapped

from ._user_roles import UserRole
from ._base import BaseModel

if TYPE_CHECKING:
    from .tasks import Task
    from .documents import Document
    from .users import User


class CommentType(enum.Enum):
    error = "Ошибка"
    comment = "Комментарий"
    status_change = "Изменение статуса"
    date_change = "Изменение даты"
    user_change = "Смена пользователя"
    notified = "Прочитал уведомление"


class CommentUserRoleAssociation(BaseModel):
    __tablename__ = 'comment_userrole_association'
    comment_id = Column(Integer, ForeignKey('comments.id'), primary_key=True)
    author_role = Column(Enum(UserRole), nullable=False, primary_key=True)
    comment = relationship('Comment', back_populates='author_roles_relation')


class Comment(BaseModel):
    __tablename__ = 'comments'

    type: Mapped[CommentType] = Column(Enum(CommentType), nullable=False)
    task_id: Mapped[int] = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=True)
    content: Mapped[str] = Column(Text, nullable=True)
    extra_data: Mapped[dict] = Column(JSON, nullable=True)
    previous_status: Mapped[str] = Column(String(50), nullable=True)
    new_status: Mapped[str] = Column(String(50), nullable=True)
    old_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)
    new_date: Mapped[DateTime] = Column(DateTime(timezone=True), nullable=True)

    task: Mapped['Task'] = relationship('Task', back_populates='comments')
    user: Mapped['User'] = relationship('User', back_populates='comments')
    documents: Mapped[List['Document']] = relationship('Document', back_populates='comment')
    author_roles_relation = relationship(
        'CommentUserRoleAssociation',
        back_populates='comment',
        cascade='all, delete-orphan',
        lazy='joined'
    )

    @property
    def author_roles(self):
        return [assoc.author_role for assoc in self.author_roles_relation]

    @author_roles.setter
    def author_roles(self, roles: List[UserRole]):
        self.author_roles_relation = [CommentUserRoleAssociation(author_role=role) for role in roles]

    def __init__(self, **kwargs):
        if 'author_roles' in kwargs:
            roles = kwargs.pop('author_roles')
            super().__init__(**kwargs)
            self.author_roles = roles
        else:
            super().__init__(**kwargs)