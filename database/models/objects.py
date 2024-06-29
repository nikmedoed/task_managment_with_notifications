from ._base import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey, Float

from sqlalchemy.orm import relationship
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .tasks import Task
    from .organizations import Organization


class Object(BaseModel):
    __tablename__ = 'objects'

    name: str = Column(String(100), nullable=False)
    organization_id: int = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    description: str = Column(String(500), nullable=True)
    address: str = Column(String(200), nullable=True)
    area_sq_meters: float = Column(Float, nullable=True)
    num_apartments: int = Column(Integer, nullable=True)

    organization: 'Organization' = relationship('Organization', back_populates='objects')
    tasks: List['Task'] = relationship('Task', back_populates='object', order_by='Task.id')
