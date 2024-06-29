from ._base import BaseModel
from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.orm import relationship
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks import Task
    from .power_of_attorneys import PowerOfAttorney
    from .comments import Comment
    from .documents import Document


class User(BaseModel):
    __tablename__ = 'users'

    last_name: str = Column(String(100), nullable=False)
    first_name: str = Column(String(100), nullable=False)
    middle_name: str = Column(String(100), nullable=True)
    email: str = Column(String(100), nullable=True, unique=True)
    phone_number: str = Column(String(15), nullable=True)
    telegram_nick: str = Column(String(50), nullable=True)
    telegram_id: int = Column(Integer, nullable=False, unique=True)
    position: str = Column(String(100), nullable=False)
    verificated: bool = Column(Boolean, nullable=False, default=False)
    active: bool = Column(Boolean, nullable=False, default=True)
    admin: bool = Column(Boolean, nullable=False, default=False)

    tasks_as_supplier: List['Task'] = relationship('Task', foreign_keys='Task.supplier_id', back_populates='supplier', order_by='Task.id')
    tasks_as_supervisor: List['Task'] = relationship('Task', foreign_keys='Task.supervisor_id', back_populates='supervisor', order_by='Task.id')
    tasks_as_executor: List['Task'] = relationship('Task', foreign_keys='Task.executor_id', back_populates='executor', order_by='Task.id')
    power_of_attorneys: List['PowerOfAttorney'] = relationship('PowerOfAttorney', back_populates='user', order_by='PowerOfAttorney.id', overlaps="user")
    comments: List['Comment'] = relationship('Comment', back_populates='user', order_by='Comment.id')
    documents: List['Document'] = relationship('Document', back_populates='author', order_by='Document.id')
