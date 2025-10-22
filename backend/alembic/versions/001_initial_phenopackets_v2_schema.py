"""Initial phenopackets v2 schema

Revision ID: 001_initial_v2
Revises:
Create Date: 2025-09-29 15:15:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_v2"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all Phenopackets v2 tables from scratch."""
    # Create phenopackets table
    op.create_table(
        "phenopackets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phenopacket_id", sa.String(100), nullable=False),
        sa.Column("version", sa.String(10), nullable=False, server_default="2.0"),
        sa.Column(
            "phenopacket", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("subject_id", sa.String(100), nullable=True),
        sa.Column("subject_sex", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column(
            "schema_version", sa.String(20), nullable=False, server_default="2.0.0"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phenopacket_id"),
    )

    # Create indexes for phenopackets
    op.create_index(
        op.f("ix_phenopackets_phenopacket_id"),
        "phenopackets",
        ["phenopacket_id"],
        unique=True,
    )
    op.create_index(op.f("ix_phenopackets_subject_id"), "phenopackets", ["subject_id"])
    op.create_index(
        op.f("ix_phenopackets_subject_sex"), "phenopackets", ["subject_sex"]
    )

    # Create GIN indexes for JSONB queries
    op.create_index(
        "idx_phenopacket_jsonb", "phenopackets", ["phenopacket"], postgresql_using="gin"
    )
    op.create_index(
        "idx_phenopacket_subject",
        "phenopackets",
        [sa.text("(phenopacket -> 'subject')")],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_phenopacket_features",
        "phenopackets",
        [sa.text("(phenopacket -> 'phenotypic_features')")],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_phenopacket_interpretations",
        "phenopackets",
        [sa.text("(phenopacket -> 'interpretations')")],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_phenopacket_diseases",
        "phenopackets",
        [sa.text("(phenopacket -> 'diseases')")],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_phenopacket_measurements",
        "phenopackets",
        [sa.text("(phenopacket -> 'measurements')")],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_phenopacket_medical_actions",
        "phenopackets",
        [sa.text("(phenopacket -> 'medical_actions')")],
        postgresql_using="gin",
    )

    # Text search indexes
    op.create_index(
        "idx_phenopacket_text_search",
        "phenopackets",
        [sa.text("to_tsvector('english', phenopacket::text)")],
        postgresql_using="gin",
    )

    # HPO term index for fast phenotype queries
    op.create_index(
        "idx_phenopacket_hpo_terms",
        "phenopackets",
        [
            sa.text(
                "jsonb_path_query_array(phenopacket, '$.phenotypic_features[*].type.id')"
            )
        ],
        postgresql_using="gin",
    )

    # Variant label index
    op.create_index(
        "idx_phenopacket_variant_labels",
        "phenopackets",
        [
            sa.text(
                "jsonb_path_query_array(phenopacket, '$.interpretations[*].diagnosis.genomic_interpretations[*].variant_interpretation.variation_descriptor.label')"
            )
        ],
        postgresql_using="gin",
    )

    # Create families table
    op.create_table(
        "families",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", sa.String(100), nullable=False),
        sa.Column("proband_id", sa.String(100), nullable=True),
        sa.Column("pedigree", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "files",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id"),
    )

    op.create_index(
        op.f("ix_families_family_id"), "families", ["family_id"], unique=True
    )
    op.create_index(op.f("ix_families_proband_id"), "families", ["proband_id"])

    # Create cohorts table
    op.create_table(
        "cohorts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cohort_id", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "members",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id"),
    )

    op.create_index(op.f("ix_cohorts_cohort_id"), "cohorts", ["cohort_id"], unique=True)

    # Create resources table
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("namespace_prefix", sa.String(50), nullable=True),
        sa.Column("iri_prefix", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id"),
    )

    op.create_index(
        op.f("ix_resources_resource_id"), "resources", ["resource_id"], unique=True
    )

    # Create phenopacket_audit table
    op.create_table(
        "phenopacket_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phenopacket_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("changed_by", sa.String(100), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_phenopacket_audit_phenopacket_id"),
        "phenopacket_audit",
        ["phenopacket_id"],
    )


def downgrade() -> None:
    """Drop all Phenopackets v2 tables."""
    # Drop audit table
    op.drop_index(
        op.f("ix_phenopacket_audit_phenopacket_id"), table_name="phenopacket_audit"
    )
    op.drop_table("phenopacket_audit")

    # Drop resources table
    op.drop_index(op.f("ix_resources_resource_id"), table_name="resources")
    op.drop_table("resources")

    # Drop cohorts table
    op.drop_index(op.f("ix_cohorts_cohort_id"), table_name="cohorts")
    op.drop_table("cohorts")

    # Drop families table
    op.drop_index(op.f("ix_families_proband_id"), table_name="families")
    op.drop_index(op.f("ix_families_family_id"), table_name="families")
    op.drop_table("families")

    # Drop phenopackets table indexes
    op.drop_index("idx_phenopacket_variant_labels", table_name="phenopackets")
    op.drop_index("idx_phenopacket_hpo_terms", table_name="phenopackets")
    op.drop_index("idx_phenopacket_text_search", table_name="phenopackets")
    op.drop_index("idx_phenopacket_medical_actions", table_name="phenopackets")
    op.drop_index("idx_phenopacket_measurements", table_name="phenopackets")
    op.drop_index("idx_phenopacket_diseases", table_name="phenopackets")
    op.drop_index("idx_phenopacket_interpretations", table_name="phenopackets")
    op.drop_index("idx_phenopacket_features", table_name="phenopackets")
    op.drop_index("idx_phenopacket_subject", table_name="phenopackets")
    op.drop_index("idx_phenopacket_jsonb", table_name="phenopackets")
    op.drop_index(op.f("ix_phenopackets_subject_sex"), table_name="phenopackets")
    op.drop_index(op.f("ix_phenopackets_subject_id"), table_name="phenopackets")
    op.drop_index(op.f("ix_phenopackets_phenopacket_id"), table_name="phenopackets")
    op.drop_table("phenopackets")
