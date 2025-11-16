"""Phenopackets v2 SQLAlchemy models and Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    updated_by: Mapped[Optional[str]] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(20), default="2.0.0")


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
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    change_patch: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)


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
    """Request model for creating a phenopacket."""

    phenopacket: Dict[str, Any]
    created_by: Optional[str] = None


class PhenopacketUpdate(BaseModel):
    """Request model for updating a phenopacket."""

    phenopacket: Dict[str, Any]
    updated_by: Optional[str] = None


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

    class Config:
        """Pydantic config for ORM mode."""

        from_attributes = True


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


class AggregationResult(BaseModel):
    """Result of aggregation queries."""

    label: str
    count: int
    percentage: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
