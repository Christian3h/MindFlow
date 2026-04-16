from sqlalchemy import Column, String, Text, func
from .database import Base


class Secret(Base):
    __tablename__ = "secrets"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    created_at = Column(String, server_default=func.now())
