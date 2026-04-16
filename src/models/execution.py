from sqlalchemy import Column, String, Text, ForeignKey, func
from .database import Base


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True)
    flow_id = Column(String, ForeignKey("flows.id"), nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(String, nullable=True)
    finished_at = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    context = Column(Text, nullable=True)
