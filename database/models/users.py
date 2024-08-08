from typing import List, TYPE_CHECKING

from sqlalchemy import Column, String, Boolean, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from ._base import BaseModel

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
    email: str = Column(String(100), nullable=True)
    phone_number: str = Column(String(15), nullable=True)
    telegram_nick: str = Column(String(50), nullable=True)
    telegram_id: int = Column(BigInteger, nullable=False, unique=True, index=True)
    position: str = Column(String(100), nullable=False)
    verificated: bool = Column(Boolean, nullable=False, default=False)
    active: bool = Column(Boolean, nullable=False, default=True)
    admin: bool = Column(Boolean, nullable=False, default=False)

    tasks_as_supplier: List['Task'] = relationship('Task', foreign_keys='Task.supplier_id', back_populates='supplier',
                                                   order_by='Task.id')
    tasks_as_supervisor: List['Task'] = relationship('Task', foreign_keys='Task.supervisor_id',
                                                     back_populates='supervisor', order_by='Task.id')
    tasks_as_executor: List['Task'] = relationship('Task', foreign_keys='Task.executor_id', back_populates='executor',
                                                   order_by='Task.id')

    issued_powers_of_attorney: List['PowerOfAttorney'] = relationship('PowerOfAttorney',
                                                                      foreign_keys='PowerOfAttorney.issuer_id',
                                                                      back_populates='issuer',
                                                                      order_by='PowerOfAttorney.id',
                                                                      overlaps="issued_powers_of_attorney")
    received_powers_of_attorney: List['PowerOfAttorney'] = relationship('PowerOfAttorney',
                                                                        foreign_keys='PowerOfAttorney.receiver_id',
                                                                        back_populates='receiver',
                                                                        order_by='PowerOfAttorney.id',
                                                                        overlaps="received_powers_of_attorney")

    comments: List['Comment'] = relationship('Comment', back_populates='user', order_by='Comment.id')
    documents: List['Document'] = relationship('Document', back_populates='author', order_by='Document.id')

    @hybrid_property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @hybrid_property
    def full_name(self):
        middle = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.last_name} {self.first_name}{middle}"

    @property
    def telegram_link(self):
        if self.telegram_nick:
            return f"https://t.me/{self.telegram_nick}"

    @hybrid_property
    def short_name(self):
        middle_initial = f" {self.middle_name[0]}." if self.middle_name else ""
        return f"{self.last_name} {self.first_name[0]}.{middle_initial}"
