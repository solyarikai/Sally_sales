"""Telegram client chat monitoring models."""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, JSON, ForeignKey, Index
from app.db import Base


class TelegramChat(Base):
    """A monitored Telegram group chat linked to a project."""
    __tablename__ = "telegram_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    chat_title = Column(String(255))
    chat_type = Column(String(50))  # group, supergroup, private
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    is_active = Column(Integer, default=1)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)


class TelegramChatMessage(Base):
    """Individual message from a monitored chat."""
    __tablename__ = "telegram_chat_messages"
    __table_args__ = (
        Index("ix_tcm_chat_date", "chat_id", "sent_at"),
    )

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False)
    sender_id = Column(BigInteger, nullable=True)
    sender_name = Column(String(255))
    sender_username = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    reply_to_message_id = Column(BigInteger, nullable=True)
    sent_at = Column(DateTime, nullable=False)
    stored_at = Column(DateTime, default=datetime.utcnow)
    message_type = Column(String(50), default="text")  # text, photo, document, sticker, etc.
    raw_data = Column(JSON, nullable=True)


class TelegramChatInsight(Base):
    """AI-extracted insights from chat messages — topics discovered from real data, not pre-defined."""
    __tablename__ = "telegram_chat_insights"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    topic = Column(String(100), nullable=False)  # discovered from data, not enum
    summary = Column(Text, nullable=False)
    key_points = Column(JSON, nullable=True)  # list of strings
    action_items = Column(JSON, nullable=True)  # list of strings
    message_ids = Column(JSON, nullable=True)  # list of message_ids that contributed
    first_message_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
