"""Initial schema.

Revision ID: 20250513_100000
Revises:
Create Date: 2025-05-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250513_100000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # raw_events
    op.create_table(
        "raw_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("project", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("raw_events") as batch_op:
        batch_op.create_unique_constraint("uq_raw_events_dedup", ["source", "event_type", "external_id"])
        batch_op.create_index("ix_raw_events_source_timestamp", ["source", "timestamp"])
        batch_op.create_index("ix_raw_events_actor", ["actor"])
        batch_op.create_index("ix_raw_events_project", ["project"])

    # sprints
    op.create_table(
        "sprints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("project", sa.String(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
    )

    # persons
    op.create_table(
        "persons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    # person_identities
    op.create_table(
        "person_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("profile_url", sa.String(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
    )
    with op.batch_alter_table("person_identities") as batch_op:
        batch_op.create_unique_constraint("uq_person_identity_source_ext", ["source", "external_id"])

    # ingestion_runs
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("events_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.create_index("ix_ingestion_runs_source_event_started", ["source", "event_type", "started_at"])


def downgrade() -> None:
    with op.batch_alter_table("ingestion_runs") as batch_op:
        batch_op.drop_index("ix_ingestion_runs_source_event_started")
    op.drop_table("ingestion_runs")
    with op.batch_alter_table("person_identities") as batch_op:
        batch_op.drop_constraint("uq_person_identity_source_ext")
    op.drop_table("person_identities")
    op.drop_table("persons")
    op.drop_table("sprints")
    with op.batch_alter_table("raw_events") as batch_op:
        batch_op.drop_index("ix_raw_events_project")
        batch_op.drop_index("ix_raw_events_actor")
        batch_op.drop_index("ix_raw_events_source_timestamp")
        batch_op.drop_constraint("uq_raw_events_dedup")
    op.drop_table("raw_events")
