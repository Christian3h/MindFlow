from sqlalchemy import Column, String, Text
from .database import Base


class NodeRegistry(Base):
    __tablename__ = "nodes_registry"

    type = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    config_schema = Column(Text, nullable=True)
    handler = Column(String, nullable=True)
