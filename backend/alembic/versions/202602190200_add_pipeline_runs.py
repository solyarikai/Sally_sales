"""add pipeline_runs, pipeline_phase_logs, cost_events tables

Revision ID: 202602190200
Revises: 202602190100
Create Date: 2026-02-19 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602190200'
down_revision: Union[str, None] = '202602190100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL to avoid SQLAlchemy's enum auto-creation issues with asyncpg
    conn = op.get_bind()

    # Create enum types (idempotent)
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE pipeline_run_status AS ENUM ('PENDING', 'RUNNING', 'PAUSED', 'STOPPED', 'COMPLETED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE pipeline_phase AS ENUM ('SEARCH', 'EXTRACTION', 'ENRICHMENT', 'VERIFICATION', 'CRM_PROMOTE', 'SMARTLEAD_PUSH');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE pipeline_phase_status AS ENUM ('STARTED', 'COMPLETED', 'FAILED', 'SKIPPED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # Create tables with raw SQL to avoid SQLAlchemy trying to re-create enums
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            status pipeline_run_status NOT NULL DEFAULT 'PENDING',
            current_phase pipeline_phase,
            config JSONB,
            progress JSONB,
            total_cost_usd NUMERIC(10,4) DEFAULT 0,
            budget_limit_usd NUMERIC(10,4),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_pipeline_runs_project_id ON pipeline_runs (project_id)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS pipeline_phase_logs (
            id SERIAL PRIMARY KEY,
            pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
            phase pipeline_phase NOT NULL,
            status pipeline_phase_status NOT NULL,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            stats JSONB,
            cost_usd NUMERIC(10,4) DEFAULT 0,
            error_message TEXT
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_pipeline_phase_logs_run_id ON pipeline_phase_logs (pipeline_run_id)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cost_events (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
            service VARCHAR(50) NOT NULL,
            units INTEGER NOT NULL DEFAULT 1,
            cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
            description VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cost_events_project_id ON cost_events (project_id)"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cost_events")
    op.execute("DROP TABLE IF EXISTS pipeline_phase_logs")
    op.execute("DROP TABLE IF EXISTS pipeline_runs")
    op.execute("DROP TYPE IF EXISTS pipeline_phase_status")
    op.execute("DROP TYPE IF EXISTS pipeline_phase")
    op.execute("DROP TYPE IF EXISTS pipeline_run_status")
