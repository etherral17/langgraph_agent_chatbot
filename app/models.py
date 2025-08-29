from sqlalchemy import Column, Integer, String, JSON, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
import datetime
from sqlalchemy.sql import func
Base = declarative_base()

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(128), index=True, nullable=True)
    input_payload = Column(JSON, nullable=False)
    result_payload = Column(JSON, nullable=True)
    logs = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
