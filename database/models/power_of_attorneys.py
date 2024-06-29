from ._base import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship, Mapped
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .users import User
    from .documents import Document
    from .organizations import Organization


class PowerOfAttorney(BaseModel):
    __tablename__ = 'power_of_attorneys'

    user_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=False)
    document_id: Mapped[int] = Column(Integer, ForeignKey('documents.id'), nullable=False)
    organization_id: Mapped[int] = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    number: Mapped[str] = Column(String(50), nullable=False)
    issue_date: Mapped[Date] = Column(Date, nullable=False)
    expiration_date: Mapped[Date] = Column(Date, nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='power_of_attorneys')
    document: Mapped['Document'] = relationship('Document', back_populates='power_of_attorneys')
    organization: Mapped['Organization'] = relationship('Organization', back_populates='power_of_attorneys')
