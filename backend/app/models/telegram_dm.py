"""Telegram DM Account model — manages Telethon user sessions for DM outreach."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func

from app.db.database import Base


class TelegramDMAccount(Base):
    __tablename__ = "telegram_dm_accounts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), default=1)

    # Telegram identity (filled after auth)
    phone = Column(String(30), nullable=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Telethon StringSession — DB-stored, not filesystem
    string_session = Column(Text, nullable=True)

    # Auth state: active | disconnected | error
    auth_status = Column(String(30), default="active")

    # Connection health
    is_connected = Column(Boolean, default=False)
    last_connected_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime, nullable=True)

    # Project assignment
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # Optional per-account proxy
    proxy_config = Column(JSON, nullable=True)

    # Polling cursor — timestamp of last processed inbound message
    last_processed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
