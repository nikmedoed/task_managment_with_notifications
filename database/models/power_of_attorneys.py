from typing import TYPE_CHECKING, List

from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship, Mapped

from ._base import BaseModel

if TYPE_CHECKING:
    from .users import User
    from .documents import Document
    from .organizations import Organization


class PowerOfAttorney(BaseModel):
    __tablename__ = 'power_of_attorneys'

    issuer_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=False)
    receiver_id: Mapped[int] = Column(Integer, ForeignKey('users.id'), nullable=False)
    organization_id: Mapped[int] = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    number: Mapped[str] = Column(String(50), nullable=False)
    issue_date: Mapped[Date] = Column(Date, nullable=False)
    expiration_date: Mapped[Date] = Column(Date, nullable=False)

    issuer: Mapped['User'] = relationship('User', foreign_keys=[issuer_id],
                                          back_populates='issued_powers_of_attorney')
    receiver: Mapped['User'] = relationship('User', foreign_keys=[receiver_id],
                                            back_populates='received_powers_of_attorney')
    documents: Mapped[List['Document']] = relationship('Document', back_populates='power_of_attorney')
    organization: Mapped['Organization'] = relationship('Organization', back_populates='power_of_attorneys')
