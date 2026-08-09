"""Add operational source-import identities and immutable run accounting.

Revision ID: c0f422b00004
Revises: b9f422b00003
Create Date: 2026-08-09
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c0f422b00004"
down_revision = "b9f422b00003"
branch_labels = None
depends_on = None

OPERATIONAL_TABLES = {
    "source_datasets",
    "source_snapshots",
    "source_import_runs",
    "phenopacket_subject_bindings",
    "source_report_bindings",
    "source_correction_registry",
}


def upgrade() -> None:
    """Add only provenance and import-control storage; clinical data stays JSONB."""
    op.add_column(
        "phenopackets",
        sa.Column(
            "provenance_status",
            sa.String(length=24),
            nullable=False,
            server_default="legacy_unbound",
        ),
    )
    op.create_check_constraint(
        "ck_phenopackets_provenance_status",
        "phenopackets",
        "provenance_status IN ('source_bound', 'legacy_unbound', 'manual')",
    )
    op.create_table(
        "source_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_system", sa.Text(), nullable=False),
        sa.Column("dataset_key", sa.Text(), nullable=False),
        sa.Column("subject_namespace", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("source_system", "dataset_key"),
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("expected_counts", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["source_datasets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dataset_id", "manifest_sha256"),
    )
    op.create_table(
        "source_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transformer_version", sa.String(length=80), nullable=False),
        sa.Column("projection_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="staged"),
        sa.Column("observed_counts", postgresql.JSONB()),
        sa.Column("summary_jsonb", postgresql.JSONB()),
        sa.Column("error_report", postgresql.JSONB()),
        sa.Column("actor_id", sa.BigInteger()),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('staged', 'validated', 'applying', 'applied', 'failed')",
            name="ck_source_import_run_status",
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ux_source_import_runs_one_applied",
        "source_import_runs",
        ["snapshot_id", "transformer_version", "projection_version"],
        unique=True,
        postgresql_where=sa.text("status = 'applied'"),
    )
    op.create_table(
        "phenopacket_subject_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_subject_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["phenopackets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_id"], ["source_datasets.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dataset_id", "source_subject_id"),
    )
    op.create_table(
        "source_report_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", sa.Text(), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_seen_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_seen_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["dataset_id"], ["source_datasets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["record_id"], ["phenopackets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["first_seen_run_id"], ["source_import_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_seen_run_id"], ["source_import_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dataset_id", "report_id"),
        sa.UniqueConstraint("record_id", "observation_id"),
    )
    op.create_table(
        "source_correction_registry",
        sa.Column("correction_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_revision_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["record_id"], ["phenopackets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_revision_id"], ["phenopacket_revisions.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    """Permit pre-activation schema rollback only; never delete activated evidence."""
    if os.environ.get("ALLOW_PREACTIVATION_SOURCE_IMPORT_DOWNGRADE") != "1":
        raise RuntimeError(
            "refusing source-import downgrade after activation; use head-pointer rollback/PITR"
        )
    for table in (
        "source_correction_registry",
        "source_report_bindings",
        "phenopacket_subject_bindings",
        "source_import_runs",
        "source_snapshots",
        "source_datasets",
    ):
        op.drop_table(table)
    op.drop_constraint(
        "ck_phenopackets_provenance_status", "phenopackets", type_="check"
    )
    op.drop_column("phenopackets", "provenance_status")
