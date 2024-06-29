from ._base import BaseModel
from sqlalchemy import Column, String, Boolean


class TaskType(BaseModel):
    __tablename__ = 'task_types'

    name: str = Column(String(50), nullable=False, unique=True)
    active: bool = Column(Boolean, nullable=False, default=True)
