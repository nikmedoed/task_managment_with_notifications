from ._base import BaseModel
from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import Object
    from .power_of_attorneys import PowerOfAttorney


class Organization(BaseModel):
    __tablename__ = 'organizations'

    name: str = Column(String(150), nullable=False)
    description: str = Column(Text, nullable=True)
    address: str = Column(String(200), nullable=True)

    objects: List['Object'] = relationship('Object', back_populates='organization', order_by='Object.id')
    power_of_attorneys: List['PowerOfAttorney'] = relationship('PowerOfAttorney', back_populates='organization', order_by='PowerOfAttorney.id', overlaps="organization")
