"""Phenopackets v2 SQLAlchemy models and Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# SQLAlchemy Models
class Phenopacket(Base):
    """Core phenopacket storage model.

    Fields:
        - version: GA4GH Phenopackets schema version (String, e.g., "2.0")
        - schema_version: Detailed schema version (String, e.g., "2.0.0")
        - revision: Optimistic locking counter (Integer, increments on update)
    """

    __tablename__ = "phenopackets"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core fields
    phenopacket_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(
        String(10),
        default="2.0",
        comment="GA4GH Phenopackets schema version (e.g., '2.0', '2.1')",
    )
    phenopacket: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Optimistic locking
    revision: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Revision counter for optimistic locking (increments on each update)",
    )

    # Denormalized fields (computed from JSONB)
    subject_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    subject_sex: Mapped[Optional[str]] = mapped_column(String(20), index=True)

    # Full-text search vector
    search_vector: Mapped[Optional[Any]] = mapped_column(
        TSVECTOR, nullable=True, index=True
    )

    # Generated columns for server-side sorting (computed by PostgreSQL)
    # These are STORED generated columns that auto-update when phenopacket changes
    # SQLAlchemy Computed() tells ORM these are server-managed, preventing INSERT errors
    features_count: Mapped[Optional[int]] = mapped_column(
        Computed(
            "jsonb_array_length("
            "COALESCE(phenopacket->'phenotypicFeatures', '[]'::jsonb))",
            persisted=True,
        ),
        comment="Count of phenotypicFeatures (auto-computed by PostgreSQL)",
    )
    has_variant: Mapped[Optional[bool]] = mapped_column(
        Computed(
            "jsonb_array_length("
            "COALESCE(phenopacket->'interpretations', '[]'::jsonb)) > 0",
            persisted=True,
        ),
        comment="Has genomic interpretations (auto-computed by PostgreSQL)",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Audit actor FKs (Wave 5a): reference users.id instead of storing a
    # free-form username. Nullable so we don't lose history when a user
    # is deleted (ON DELETE SET NULL). Username is rendered through the
    # ``*_by_user`` relationships below for API responses.
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")

    # Soft delete fields
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when record was soft-deleted (NULL if active)",
    )
    deleted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User id who performed the soft delete",
    )

    # Relationships to resolve username from FK. ``viewonly=True`` so
    # ORM flushes don't try to back-populate the User side — we only
    # read these relationships when rendering responses. The
    # repository's ``_with_actor_eager_loads`` helper applies
    # ``selectinload`` on every read path that is eventually rendered
    # through ``build_phenopacket_response``; after ``session.refresh``
    # on a freshly-committed phenopacket, callers that need the
    # username must re-fetch via ``get_by_id`` to re-apply the eager
    # loads (the service layer does this).
    created_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[created_by_id], viewonly=True
    )
    updated_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[updated_by_id], viewonly=True
    )
    deleted_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[deleted_by_id], viewonly=True
    )

    # Wave 7 D.1: state machine columns
    state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    editing_revision_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("phenopacket_revisions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    head_published_revision_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("phenopacket_revisions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    draft_owner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_owner: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[draft_owner_id], viewonly=True
    )
    editing_revision: Mapped[Optional["PhenopacketRevision"]] = relationship(
        "PhenopacketRevision",
        foreign_keys=[editing_revision_id],
        viewonly=True,
        primaryjoin="Phenopacket.editing_revision_id==PhenopacketRevision.id",
    )


class Family(Base):
    """Family relationships model."""

    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    family_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    family_phenopacket: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    proband_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    pedigree: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    files: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Cohort(Base):
    """Cohort model for population studies."""

    __tablename__ = "cohorts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cohort_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    cohort_phenopacket: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    members: Mapped[List[str]] = mapped_column(JSONB, default=list)
    meta_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Resource(Base):
    """Resource metadata for ontologies and data sources."""

    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    namespace_prefix: Mapped[Optional[str]] = mapped_column(String(50))
    url: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    iri_prefix: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PhenopacketAudit(Base):
    """Audit log for phenopacket changes."""

    __tablename__ = "phenopacket_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phenopacket_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User id of the actor who performed the change",
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    change_patch: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)

    # Relationship for resolving the actor's username on read. viewonly
    # because audit rows are immutable once written.
    changed_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[changed_by_id], viewonly=True
    )


class PhenopacketRevision(Base):
    """Immutable snapshot of a phenopacket at a state transition.

    Each row represents one revision of a phenopacket, created when the
    record transitions between workflow states or when a draft is saved.

    See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.2.
    """

    __tablename__ = "phenopacket_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phenopackets.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    content_jsonb: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_patch: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
    )
    from_state: Mapped[Optional[str]] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    is_head_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id], viewonly=True)


# Pydantic Schemas for API
class OntologyClass(BaseModel):
    """Ontology term reference."""

    id: str
    label: Optional[str] = None


class TimeElement(BaseModel):
    """Time element for onset, age, and other temporal data."""

    age: Optional[Dict[str, str]] = None  # iso8601duration
    age_range: Optional[Dict[str, Any]] = None
    ontology_class: Optional[OntologyClass] = None
    timestamp: Optional[str] = None
    interval: Optional[Dict[str, Any]] = None


class Evidence(BaseModel):
    """Evidence for an assertion."""

    evidence_code: OntologyClass
    reference: Optional[Dict[str, str]] = None


class PhenotypicFeature(BaseModel):
    """Phenotypic feature observation."""

    type: OntologyClass
    excluded: Optional[bool] = False
    severity: Optional[OntologyClass] = None
    modifiers: Optional[List[OntologyClass]] = None
    onset: Optional[TimeElement] = None
    resolution: Optional[TimeElement] = None
    evidence: Optional[List[Evidence]] = None


class Measurement(BaseModel):
    """Clinical measurement."""

    assay: OntologyClass
    value: Dict[str, Any]  # Can be Quantity, OntologyClass, or other types
    time_observed: Optional[TimeElement] = None
    procedure: Optional[Dict[str, Any]] = None
    interpretation: Optional[OntologyClass] = None


class Disease(BaseModel):
    """Disease diagnosis."""

    term: OntologyClass
    excluded: Optional[bool] = False
    onset: Optional[TimeElement] = None
    resolution: Optional[TimeElement] = None
    disease_stage: Optional[List[OntologyClass]] = None
    clinical_tnm_finding: Optional[List[OntologyClass]] = None
    primary_site: Optional[OntologyClass] = None


class VariationDescriptor(BaseModel):
    """Genomic variation descriptor."""

    id: Optional[str] = None
    variation: Optional[Dict[str, Any]] = None
    label: Optional[str] = None
    description: Optional[str] = None
    gene_context: Optional[Dict[str, str]] = None
    expressions: Optional[List[Dict[str, Any]]] = None
    vcf_record: Optional[Dict[str, Any]] = None
    molecule_context: Optional[str] = None
    structural_type: Optional[OntologyClass] = None
    allelic_state: Optional[OntologyClass] = None


class VariantInterpretation(BaseModel):
    """Interpretation of a genomic variant."""

    acmg_pathogenicity_classification: Optional[str] = None
    therapeutic_actionability: Optional[str] = None
    variation_descriptor: VariationDescriptor


class GenomicInterpretation(BaseModel):
    """Genomic interpretation."""

    subject_or_biosample_id: str
    interpretation_status: str
    variant_interpretation: Optional[VariantInterpretation] = None


class Diagnosis(BaseModel):
    """Clinical diagnosis with genomic interpretations."""

    disease: OntologyClass
    genomic_interpretations: Optional[List[GenomicInterpretation]] = None


class Interpretation(BaseModel):
    """Clinical interpretation."""

    id: str
    progress_status: str
    diagnosis: Optional[Diagnosis] = None


class Treatment(BaseModel):
    """Medical treatment."""

    agent: OntologyClass
    route_of_administration: Optional[OntologyClass] = None
    dose_intervals: Optional[List[Dict[str, Any]]] = None
    drug_type: Optional[str] = None


class MedicalAction(BaseModel):
    """Medical action taken."""

    treatment: Optional[Treatment] = None
    procedure: Optional[Dict[str, Any]] = None
    radiation_therapy: Optional[Dict[str, Any]] = None
    therapeutic_regimen: Optional[OntologyClass] = None
    treatment_target: Optional[OntologyClass] = None
    treatment_intent: Optional[OntologyClass] = None
    response_to_treatment: Optional[OntologyClass] = None
    adverse_events: Optional[List[OntologyClass]] = None
    treatment_termination_reason: Optional[OntologyClass] = None


class Individual(BaseModel):
    """Individual/subject information."""

    id: str
    alternate_ids: Optional[List[str]] = None
    date_of_birth: Optional[str] = None
    time_at_last_encounter: Optional[TimeElement] = None
    vital_status: Optional[Dict[str, Any]] = None
    sex: Optional[str] = None
    karyotypic_sex: Optional[str] = None
    gender: Optional[OntologyClass] = None
    taxonomy: Optional[OntologyClass] = None


class File(BaseModel):
    """File reference."""

    uri: str
    individual_to_file_identifiers: Optional[Dict[str, str]] = None
    file_attributes: Optional[Dict[str, str]] = None


class MetaData(BaseModel):
    """Metadata for the phenopacket."""

    created: str
    created_by: str
    submitted_by: Optional[str] = None
    resources: List[Dict[str, str]]
    phenopacket_schema_version: str = "2.0.0"
    external_references: Optional[List[Dict[str, str]]] = None


class PhenopacketSchema(BaseModel):
    """Complete phenopacket schema."""

    id: str
    subject: Individual
    phenotypic_features: Optional[List[PhenotypicFeature]] = None
    measurements: Optional[List[Measurement]] = None
    biosamples: Optional[List[Dict[str, Any]]] = None
    interpretations: Optional[List[Interpretation]] = None
    diseases: Optional[List[Disease]] = None
    medical_actions: Optional[List[MedicalAction]] = None
    files: Optional[List[File]] = None
    meta_data: MetaData

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate phenopacket ID format."""
        if not v.startswith("phenopacket:"):
            v = f"phenopacket:HNF1B:{v}"
        return v


# API Request/Response Models
class PhenopacketCreate(BaseModel):
    """Request model for creating a phenopacket.

    Note: ``created_by`` is no longer accepted in the request body —
    the authenticated actor's user id is always used (Wave 5a FK-ify).
    Any ``created_by`` field in the incoming JSON is silently ignored.
    """

    phenopacket: Dict[str, Any]


class PhenopacketUpdate(BaseModel):
    """Request model for updating a phenopacket.

    Includes optional optimistic locking support via revision field and
    audit trail support via change_reason field. ``updated_by`` is no
    longer accepted — the authenticated actor is always used.
    """

    phenopacket: Dict[str, Any]
    revision: Optional[int] = Field(
        None,
        description=(
            "Optional revision for optimistic locking (disabled if not provided)"
        ),
    )
    change_reason: str = Field(
        ..., min_length=1, description="Reason for the change (audit trail)"
    )


class PhenopacketDelete(BaseModel):
    """Request model for deleting a phenopacket.

    Uses request body to avoid URL length limitations with query parameters.
    """

    change_reason: str = Field(
        ..., min_length=1, description="Reason for deletion (audit trail)"
    )
    revision: Optional[int] = Field(
        None,
        description=(
            "Optional optimistic-locking revision. If provided, the delete "
            "returns 409 Conflict when the current row revision differs."
        ),
    )


class PhenopacketResponse(BaseModel):
    """Response model for phenopacket queries."""

    id: str
    phenopacket_id: str
    version: str  # GA4GH schema version
    revision: int  # Optimistic locking counter
    phenopacket: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    schema_version: str
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    # Wave 7 D.1: state machine fields
    # Optional so non-curator callers receive state=None (spec §7.2).
    state: Optional[str] = "draft"
    head_published_revision_id: Optional[int] = None
    editing_revision_id: Optional[int] = None
    draft_owner_id: Optional[int] = None
    draft_owner_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PhenopacketSearchQuery(BaseModel):
    """Search query parameters."""

    phenotypes: Optional[List[str]] = Field(
        None, description="HPO term IDs to search for"
    )
    diseases: Optional[List[str]] = Field(
        None, description="MONDO disease IDs to search for"
    )
    variants: Optional[List[str]] = Field(
        None, description="Variant labels to search for"
    )
    measurements: Optional[List[Dict[str, str]]] = Field(
        None, description="LOINC codes for measurements"
    )
    sex: Optional[str] = Field(None, description="Subject sex filter")
    min_age: Optional[int] = Field(None, description="Minimum age in years")
    max_age: Optional[int] = Field(None, description="Maximum age in years")


class PhenopacketAuditResponse(BaseModel):
    """Response model for phenopacket audit trail entries.

    Unified view over two underlying sources:
    - ``source='audit'``    — rows from ``phenopacket_audit`` (CREATE + legacy
      pre-Wave-7 UPDATE/DELETE entries).
    - ``source='revision'`` — rows from ``phenopacket_revisions`` (Wave 7 D.1
      state-machine transitions and inplace-save drafts).

    Both sources share the common fields; revision-only fields (``state_transition``)
    are ``None`` for audit-source entries and vice versa (``old_value``,
    ``new_value``, ``change_summary``).
    """

    id: str
    phenopacket_id: str
    action: str
    changed_by: Optional[str] = None
    changed_at: datetime
    change_reason: Optional[str] = None
    change_summary: Optional[str] = None
    change_patch: Optional[Any] = None  # JSONB can store arrays or objects
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    # Wave 7 D.1: merged audit view
    source: str = "audit"  # 'audit' | 'revision'
    state_transition: Optional[Dict[str, Optional[str]]] = None  # {from, to}

    model_config = ConfigDict(from_attributes=True)


class AggregationResult(BaseModel):
    """Result of aggregation queries."""

    label: str
    count: int
    percentage: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# Wave 7 D.1: state-machine Pydantic schemas (§7.3)


class TransitionRequest(BaseModel):
    """Request body for POST /phenopackets/{id}/transitions.

    See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §7.3.
    """

    to_state: Literal[
        "draft",
        "in_review",
        "changes_requested",
        "approved",
        "published",
        "archived",
    ]
    reason: str = Field(..., min_length=1, max_length=500)
    revision: int


class RevisionResponse(BaseModel):
    """Response model for a single phenopacket revision row.

    See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §7.3.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    record_id: str  # UUID serialized as string
    # populated via join with phenopackets table
    phenopacket_id: str
    revision_number: int
    state: str
    from_state: Optional[str] = None
    to_state: str
    is_head_published: bool
    change_reason: str
    actor_id: int
    actor_username: Optional[str] = None
    change_patch: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    # populated only on /{id}/revisions/{rev_id}
    content_jsonb: Optional[Dict[str, Any]] = None
