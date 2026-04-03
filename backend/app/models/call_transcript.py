"""CallTranscript model — stores call recording transcripts from Fireflies.ai."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.db import Base
from app.models.mixins import TimestampMixin


class CallTranscript(Base, TimestampMixin):
    """Stores call recording transcripts linked to contacts."""
    __tablename__ = "call_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    fireflies_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    date = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    organizer_email = Column(String(255), nullable=True, index=True)

    participants = Column(JSON, nullable=True)  # [{name, email}]
    speakers = Column(JSON, nullable=True)  # [{id, name}]
    summary = Column(Text, nullable=True)
    action_items = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)
    transcript_text = Column(Text, nullable=True)  # full plain text
    sentences = Column(JSON, nullable=True)  # [{speaker, text, start_time, end_time}]

    transcript_url = Column(String(1000), nullable=True)
    audio_url = Column(String(1000), nullable=True)

    extra_data = Column(JSON, nullable=True)
    source = Column(String(50), default="webhook")  # webhook or manual_sync

    # Relationships
    contact = relationship("Contact", backref="call_transcripts")
    project = relationship("Project")

    __table_args__ = (
        Index('ix_call_transcripts_date', 'date'),
        Index('ix_call_transcripts_contact_date', 'contact_id', 'date'),
    )
