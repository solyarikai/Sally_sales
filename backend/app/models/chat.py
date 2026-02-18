"""
Project Chat Messages — persistent storage for chat conversations per project.
Replaces localStorage-only chat with server-side persistence.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
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

    # Enhanced chat metadata (Phase 1.2)
    action_type = Column(String(50), nullable=True)       # which CHAT_ACTION was executed
    action_data = Column(JSONB, nullable=True)             # structured data for rendering action buttons
    suggestions = Column(JSONB, nullable=True)             # suggestion chips stored for re-render
    feedback = Column(String(10), nullable=True)           # 'positive' | 'negative' | null
    tokens_used = Column(Integer, nullable=True)           # AI call cost tracking
    duration_ms = Column(Integer, nullable=True)           # response time

    __table_args__ = (
        Index("ix_project_chat_messages_project_created", "project_id", "created_at"),
        Index("ix_project_chat_messages_project_client", "project_id", "client_id", unique=True),
    )
