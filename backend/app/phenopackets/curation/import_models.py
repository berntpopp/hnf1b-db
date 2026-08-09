"""Operational import/provenance models; clinical facts remain in revision JSONB."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportRunStatus(str, Enum):
    """Allowed lifecycle states for a source import attempt."""

    STAGED = "staged"
    VALIDATED = "validated"
    APPLYING = "applying"
    APPLIED = "applied"
    FAILED = "failed"


class ImportPayloadError(ValueError):
    """Operational run metadata attempted to contain secret or clinical source data."""


_FORBIDDEN_PAYLOAD_KEY = re.compile(
    r"(?:password|passwd|secret|token|credential|email|comment|raw|row|clinical)",
    re.IGNORECASE,
)
_SAFE_TEXT = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


def sanitize_operational_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate count/digest operational metadata without silently redacting it."""

    def visit(value: Any, path: str = "") -> Any:
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for key, nested in value.items():
                key_text = str(key)
                if _FORBIDDEN_PAYLOAD_KEY.search(key_text):
                    raise ImportPayloadError(
                        f"forbidden operational payload key at {path}{key_text}"
                    )
                result[key_text] = visit(nested, f"{path}{key_text}.")
            return result
        if isinstance(value, list):
            return [visit(item, path) for item in value]
        if isinstance(value, str):
            if not _SAFE_TEXT.fullmatch(value):
                raise ImportPayloadError(
                    f"unsafe string in operational payload at {path}"
                )
            return value
        if value is None or isinstance(value, (bool, int, float)):
            return value
        raise ImportPayloadError(f"unsupported operational payload value at {path}")

    return visit(payload)


class SourceDataset(Base):
    """Stable external dataset identity; never contains source rows."""

    __tablename__ = "source_datasets"
    __table_args__ = (UniqueConstraint("source_system", "dataset_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_key: Mapped[str] = mapped_column(Text, nullable=False)
    subject_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceSnapshot(Base):
    """Content-addressed manifest for a complete, immutable source snapshot."""

    __tablename__ = "source_snapshots"
    __table_args__ = (UniqueConstraint("dataset_id", "manifest_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_datasets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceImportRun(Base):
    """One retryable import attempt, retaining only sanitized run accounting."""

    __tablename__ = "source_import_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'validated', 'applying', 'applied', 'failed')",
            name="ck_source_import_run_status",
        ),
        Index(
            "ux_source_import_runs_one_applied",
            "snapshot_id",
            "transformer_version",
            "projection_version",
            unique=True,
            postgresql_where="status = 'applied'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transformer_version: Mapped[str] = mapped_column(String(80), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ImportRunStatus.STAGED.value
    )
    observed_counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    summary_jsonb: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PhenopacketSubjectBinding(Base):
    """Dataset subject identity bound to one adjudicated individual record."""

    __tablename__ = "phenopacket_subject_bindings"
    __table_args__ = (UniqueConstraint("dataset_id", "source_subject_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phenopackets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_datasets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_subject_id: Mapped[str] = mapped_column(Text, nullable=False)


class SourceReportBinding(Base):
    """Immutable source report-to-record identity binding."""

    __tablename__ = "source_report_bindings"
    __table_args__ = (
        UniqueConstraint("dataset_id", "report_id"),
        UniqueConstraint("record_id", "observation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_datasets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_id: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phenopackets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    first_seen_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_import_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    last_seen_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_import_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class SourceCorrectionRegistry(Base):
    """Operational registry prevents correction-ID reuse with different content."""

    __tablename__ = "source_correction_registry"

    correction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phenopackets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_revision_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("phenopacket_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
