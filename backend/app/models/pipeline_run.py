"""
Pipeline Run models — DB-backed pipeline state machine, phase logging, and cost tracking.

Replaces in-memory _running_pipelines dict with persistent state that survives restarts.
"""
import enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db import Base


class PipelineRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelinePhase(str, enum.Enum):
    SEARCH = "SEARCH"
    EXTRACTION = "EXTRACTION"
    ENRICHMENT = "ENRICHMENT"
    VERIFICATION = "VERIFICATION"
    CRM_PROMOTE = "CRM_PROMOTE"
    SMARTLEAD_PUSH = "SMARTLEAD_PUSH"


class PipelinePhaseStatus(str, enum.Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)

    status = Column(
        Enum(PipelineRunStatus, name="pipeline_run_status", create_type=False),
        nullable=False,
        default=PipelineRunStatus.PENDING,
    )
    current_phase = Column(
        Enum(PipelinePhase, name="pipeline_phase", create_type=False),
        nullable=True,
    )

    config = Column(JSONB, nullable=True)         # what was requested (FullPipelineRequest)
    progress = Column(JSONB, nullable=True)        # live progress data
    total_cost_usd = Column(Numeric(10, 4), default=0)
    budget_limit_usd = Column(Numeric(10, 4), nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PipelinePhaseLog(Base):
    __tablename__ = "pipeline_phase_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(
        Enum(PipelinePhase, name="pipeline_phase", create_type=False),
        nullable=False,
    )
    status = Column(
        Enum(PipelinePhaseStatus, name="pipeline_phase_status", create_type=False),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    stats = Column(JSONB, nullable=True)
    cost_usd = Column(Numeric(10, 4), default=0)
    error_message = Column(Text, nullable=True)


class CostEvent(Base):
    __tablename__ = "cost_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)

    service = Column(String(50), nullable=False)   # yandex, google, apollo, crona, findymail, gemini, openai
    units = Column(Integer, nullable=False, default=1)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
