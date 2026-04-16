from sqlalchemy import Column, String, Text, Integer, func
from .database import Base


class Flow(Base):
    __tablename__ = "flows"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Integer, default=0)
    trigger_type = Column(String, nullable=True)
    trigger_config = Column(Text, nullable=True)
    nodes = Column(Text, nullable=False)
    data_path = Column(Text, nullable=True)
    created_at = Column(String, server_default=func.now())
    updated_at = Column(String, server_default=func.now(), onupdate=func.now())
