# File: app/models.py
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd  # Used for consistent date parsing
from bson import ObjectId as BsonObjectId  # Provided by PyMongo
from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------------------
# Utility function: Convert NA (or NaN) values to None.
def none_if_nan(v):
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    return v


# ------------------------------------------------------------------------------
# Helper function for parsing dates using Pandas (returns a datetime)
def parse_date_value(value) -> Optional[datetime]:
    try:
        if value is None:
            return None
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isnull(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


# ------------------------------------------------------------------------------
# Custom type for MongoDB ObjectId.
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if isinstance(v, BsonObjectId):
            return str(v)
        if isinstance(v, str):
            return v
        raise TypeError("Invalid type for ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}


# ------------------------------------------------------------------------------
# User model
class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: int
    user_name: str
    password: str
    email: str
    user_role: str
    first_name: str
    family_name: str
    orcid: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }


# ------------------------------------------------------------------------------
# Phenotype sub-model for reports
class Phenotype(BaseModel):
    phenotype_id: str
    name: str
    modifier: Optional[Dict[str, Optional[str]]] = None
    described: str

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# Report model (to be embedded in an Individual)
class Report(BaseModel):
    report_id: str  # Changed from int to str
    reviewed_by: Optional[PyObjectId] = None
    phenotypes: Dict[str, Phenotype] = Field(default_factory=dict)
    publication_ref: Optional[PyObjectId] = None
    review_date: Optional[datetime] = None
    comment: Optional[str] = None
    family_history: Optional[str] = None
    age_reported: Optional[str] = None
    age_onset: Optional[str] = None
    cohort: Optional[str] = None
    report_date: Optional[datetime] = None

    model_config = {"extra": "allow"}

    @field_validator("review_date", mode="before")
    @classmethod
    def parse_review_date(cls, v):
        if not v:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v.strip(), "%m/%d/%Y %H:%M:%S")
            except Exception as e:
                raise ValueError(f"Could not parse review_date: {v}") from e
        return v

    @field_validator("report_date", mode="before")
    @classmethod
    def parse_report_date(cls, v):
        if not v:
            return None
        if isinstance(v, str):
            try:
                return parse_date_value(v)
            except Exception as e:
                raise ValueError(f"Could not parse report_date: {v}") from e
        return v

    @field_validator("report_id", mode="before")
    @classmethod
    def format_report_id(cls, v):
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            return f"rep{int(v):04d}"
        return v


# ------------------------------------------------------------------------------
# IndividualVariant model
class IndividualVariant(BaseModel):
    variant_ref: PyObjectId
    detection_method: Optional[str] = None
    segregation: Optional[str] = None

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# Individual model
class Individual(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    individual_id: str
    Sex: Optional[str] = None
    individual_DOI: Optional[str] = None
    DupCheck: Optional[str] = None
    IndividualIdentifier: Optional[str] = None
    Problematic: str = ""
    reports: List[Report] = Field(default_factory=list)
    variant: Optional[IndividualVariant] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }

    @field_validator("Problematic", mode="before")
    @classmethod
    def validate_problematic(cls, v):
        val = none_if_nan(v)
        return val if val is not None else ""

    @field_validator("individual_id", mode="before")
    @classmethod
    def format_individual_id(cls, v):
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            return f"ind{int(v):04d}"
        return v


# ------------------------------------------------------------------------------
# VariantClassifications model
class VariantClassifications(BaseModel):
    verdict: Optional[str] = None
    criteria: Optional[str] = None
    comment: Optional[str] = None
    system: Optional[str] = None
    classification_date: Optional[datetime] = None

    model_config = {"extra": "allow"}

    @field_validator("classification_date", mode="before")
    @classmethod
    def parse_classification_date(cls, v):
        return parse_date_value(v)


# ------------------------------------------------------------------------------
# VariantAnnotation model
class VariantAnnotation(BaseModel):
    transcript: Optional[str] = None
    c_dot: Optional[str] = None
    p_dot: Optional[str] = None
    source: Optional[str] = None
    annotation_date: Optional[datetime] = None

    model_config = {"extra": "allow"}

    @field_validator("annotation_date", mode="before")
    @classmethod
    def parse_annotation_date(cls, v):
        return parse_date_value(v)


# ------------------------------------------------------------------------------
# ReportedEntry model
class ReportedEntry(BaseModel):
    variant_reported: str
    publication_ref: Optional[PyObjectId] = None

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# Variant model
class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    variant_id: str
    individual_ids: List[PyObjectId] = Field(default_factory=list)
    classifications: List[VariantClassifications] = Field(default_factory=list)
    annotations: List[VariantAnnotation] = Field(default_factory=list)
    reported: List[ReportedEntry] = Field(default_factory=list)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }

    @field_validator("annotations", mode="before")
    @classmethod
    def validate_annotations(cls, v):
        return v

    @field_validator("variant_id", mode="before")
    @classmethod
    def format_variant_id(cls, v):
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            return f"var{int(v):04d}"
        return v


# ------------------------------------------------------------------------------
# Author model
class Author(BaseModel):
    lastname: Optional[str] = None
    firstname: Optional[str] = None
    initials: Optional[str] = None
    affiliations: List[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# Publication model with padded publication_id (e.g. "pub0001")
class Publication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    publication_id: str  # Now a padded identifier.
    publication_alias: str
    publication_type: Optional[str] = None
    publication_entry_date: Optional[datetime] = Field(
        default_factory=lambda: datetime(2021, 11, 1)
    )
    PMID: Optional[int] = None
    DOI: Optional[str] = None
    PDF: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    publication_date: Optional[datetime] = None
    journal_abbreviation: Optional[str] = None
    journal: Optional[str] = None
    keywords: Optional[List[str]] = Field(default_factory=list)
    medical_specialty: Optional[List[str]] = Field(default_factory=list)
    authors: List[Author] = Field(default_factory=list)
    update_date: Optional[datetime] = Field(default_factory=datetime.now)
    comment: Optional[str] = None
    assignee: Optional[PyObjectId] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }

    @field_validator("publication_id", mode="before")
    @classmethod
    def validate_publication_id(cls, v):
        # If the value is a dict with $numberInt, extract the integer.
        if isinstance(v, dict) and "$numberInt" in v:
            v = int(v["$numberInt"])
        if isinstance(v, (int, float)):
            return f"pub{int(v):04d}"
        if isinstance(v, str) and v.isdigit():
            return f"pub{int(v):04d}"
        return v

    @field_validator("PMID", mode="before")
    @classmethod
    def validate_pmid(cls, v):
        v = none_if_nan(v)
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    @field_validator("DOI", mode="before")
    @classmethod
    def validate_doi(cls, v):
        return none_if_nan(v)

    @field_validator("PDF", mode="before")
    @classmethod
    def validate_pdf(cls, v):
        return none_if_nan(v)

    @field_validator("publication_date", mode="before")
    @classmethod
    def parse_publication_date(cls, v):
        return parse_date_value(v)


# ------------------------------------------------------------------------------
# New ProteinFeature model – used for holding domain/structure information.
class ProteinFeature(BaseModel):
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    start: Optional[int] = None
    length: Optional[int] = None
    description: Optional[str] = ""
    description_short: Optional[str] = ""
    source: Optional[str] = ""
    height: Optional[int] = None

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# New Protein model – represents the protein structure and domains.
class Protein(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    gene: str
    transcript: str
    protein: str
    features: Dict[str, List[ProteinFeature]] = Field(default_factory=dict)
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }


# ------------------------------------------------------------------------------
# New Exon model for gene structure.
class Exon(BaseModel):
    exon_number: Optional[int] = None
    start: Optional[int] = None
    stop: Optional[int] = None

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------------------
# New Gene model – represents the genomic structure of the HNF1B gene.
class Gene(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    gene_symbol: str
    ensembl_gene_id: str
    transcript: str
    exons: List[Exon] = Field(default_factory=list)
    hg38: Dict[str, Any] = Field(default_factory=dict)
    hg19: Dict[str, Any] = Field(default_factory=dict)
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow",
    }


# ------------------------------------------------------------------------------
# Update forward references for self-referencing embedded models.
Individual.update_forward_refs()
