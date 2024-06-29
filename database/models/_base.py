from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped

Base = declarative_base()


class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id: Mapped[int] = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        unique=True
    )
    time_created: Mapped[DateTime] = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    time_updated: Mapped[DateTime] = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id!r})>"

    def to_dict(self) -> dict:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
