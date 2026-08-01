from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(length=256), nullable=False)
    source = Column(String(length=256), nullable=True)
    content_hash = Column(String(length=128), unique=True, nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    provider_name = Column(String(length=128), nullable=True)
    confidence = Column(Float, nullable=True)
    extraction_result = Column(Text, nullable=True)


class PortalEvent(Base):
    __tablename__ = "portal_events"

    id = Column(Integer, primary_key=True, index=True)
    portal_id = Column(String(length=128), nullable=False)
    portal_name = Column(String(length=256), nullable=False)
    action = Column(String(length=128), nullable=False)
    user_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
