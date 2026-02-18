"""
Project Chat Messages — persistent storage for chat conversations per project.
Replaces localStorage-only chat with server-side persistence.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.sql import func
from app.db import Base


class ProjectChatMessage(Base):
    __tablename__ = "project_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    client_id = Column(String(100), nullable=True)  # frontend-generated dedup key
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_project_chat_messages_project_created", "project_id", "created_at"),
        Index("ix_project_chat_messages_project_client", "project_id", "client_id", unique=True),
    )
