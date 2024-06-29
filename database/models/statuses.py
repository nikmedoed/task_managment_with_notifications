from ._base import BaseModel
from sqlalchemy import Column, String, Boolean, Text


class Status(BaseModel):
    __tablename__ = 'statuses'

    name: str = Column(String(50), nullable=False, unique=True)
    description: str = Column(Text, nullable=True)
    active: bool = Column(Boolean, nullable=False, default=True)
