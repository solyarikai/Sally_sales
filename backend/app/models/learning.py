"""
Learning System models — tracks AI learning cycles and operator corrections.

LearningLog: Records each learning cycle (manual trigger, feedback, scheduled)
OperatorCorrection: Captures diffs between AI drafts and what operators actually sent
ReferenceExample: Operator's real replies stored with embeddings for semantic retrieval
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime

from app.db import Base
from app.models.mixins import TimestampMixin


class LearningLog(Base, TimestampMixin):
    """A single learning cycle — analyzing conversations and updating templates/ICP."""
    __tablename__ = "learning_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger = Column(String(50), nullable=False)  # manual / feedback / scheduled
    conversations_analyzed = Column(Integer, nullable=True)
    conversations_email = Column(Integer, nullable=True)
    conversations_linkedin = Column(Integer, nullable=True)
    qualified_count = Column(Integer, nullable=True)
    change_type = Column(String(50), nullable=True)  # template_updated / icp_updated / both / feedback_applied
    change_summary = Column(Text, nullable=True)
    before_snapshot = Column(JSONB, nullable=True)
    after_snapshot = Column(JSONB, nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    feedback_text = Column(Text, nullable=True)  # If trigger=feedback, the user's input
    status = Column(String(30), nullable=False, default="processing")  # processing / completed / failed / insufficient_data
    error_message = Column(Text, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    template_id = Column(Integer, ForeignKey("reply_prompt_templates.id", ondelete="SET NULL"), nullable=True)
    corrections_snapshot = Column(JSONB, nullable=True)  # Full corrections data + KPI stats

    __table_args__ = (
        Index("ix_learning_logs_project_trigger", "project_id", "trigger"),
        Index("ix_learning_logs_project_created", "project_id", "created_at"),
    )


class OperatorCorrection(Base):
    """Captures every operator action on a reply — send, dismiss, regenerate."""
    __tablename__ = "operator_corrections"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    processed_reply_id = Column(Integer, ForeignKey("processed_replies.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_draft_reply = Column(Text, nullable=True)
    ai_draft_subject = Column(String(500), nullable=True)
    sent_reply = Column(Text, nullable=True)
    sent_subject = Column(String(500), nullable=True)
    was_edited = Column(Boolean, default=False, nullable=False)
    action_type = Column(String(30), default="send", nullable=False)  # send / dismiss / regenerate
    reply_category = Column(String(50), nullable=True)  # interested / meeting_request / etc
    channel = Column(String(50), nullable=True)  # email / linkedin
    lead_company = Column(String(255), nullable=True)
    lead_email = Column(String(255), nullable=True)
    campaign_name = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_operator_corrections_project_created", "project_id", "created_at"),
    )


class ReferenceExample(Base):
    """Operator's real reply stored with embedding for semantic retrieval."""
    __tablename__ = "reference_examples"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_message = Column(Text, nullable=False)
    operator_reply = Column(Text, nullable=False)
    lead_context = Column(JSONB, nullable=True)  # {name, company, role, channel, category}
    channel = Column(String(50), nullable=True)  # email / linkedin
    category = Column(String(50), nullable=True)  # interested / meeting_request / etc
    quality_score = Column(Integer, default=3)  # 1-5, auto or operator-rated
    source = Column(String(30), nullable=False)  # 'learned' / 'feedback' / 'manual'
    embedding = Column(Vector(1536), nullable=True)  # text-embedding-3-small
    thread_message_id = Column(Integer, nullable=True)  # link back to source (dedup)
    processed_reply_id = Column(Integer, nullable=True)  # link to original reply
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ref_examples_project", "project_id"),
        Index(
            "ix_ref_examples_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
