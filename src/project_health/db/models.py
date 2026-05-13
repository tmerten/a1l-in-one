"""SQLAlchemy declarative base and ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for async SQLAlchemy."""

    type_annotation_map: dict[type, type] = {
        dict[str, Any]: JSON,
        list[str]: JSON,
    }


class RawEvent(Base):
    """Raw events ingested from external data sources."""

    __tablename__ = "raw_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String, nullable=False)  # "github", "jira"
    event_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "commit", "pull_request", "pull_request_review", "issue"
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    project: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("source", "event_type", "external_id", name="uq_raw_events_dedup"),
        Index("ix_raw_events_source_timestamp", "source", "timestamp"),
        Index("ix_raw_events_actor", "actor"),
        Index("ix_raw_events_project", "project"),
    )


class Sprint(Base):
    """Jira sprint definitions."""

    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    project: Mapped[str] = mapped_column(String, nullable=False)  # Jira project key
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)  # active | closed | future


class Person(Base):
    """Canonical person record from YAML team list."""

    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)


class PersonIdentity(Base):
    """Per-source identity mapping for a person."""

    __tablename__ = "person_identities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_person_identity_source_ext"),
    )


class IngestionRun(Base):
    """Observability record for each ingestion run."""

    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="running"
    )  # running | success | failure | skipped
    trigger: Mapped[str] = mapped_column(
        String, nullable=False
    )  # scheduled | manual | backfill
    events_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ingestion_runs_source_event_started", "source", "event_type", "started_at"),
    )
