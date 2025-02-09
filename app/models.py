from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import date
import math
from bson import ObjectId as BsonObjectId  # Provided by PyMongo

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
# Custom type for MongoDB ObjectId.
class PyObjectId:
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if isinstance(v, cls):
            return v
        if isinstance(v, BsonObjectId):
            return cls(str(v))
        if isinstance(v, str):
            return cls(v)
        raise TypeError("Invalid type for PyObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}

    def __init__(self, oid: str):
        self.oid = oid

    def __str__(self):
        return self.oid

    def __repr__(self):
        return f"PyObjectId({self.oid})"

# ------------------------------------------------------------------------------
# User model (for reviewers/users)
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
        "extra": "allow"
    }

# ------------------------------------------------------------------------------
# Phenotype sub-model for reports
class Phenotype(BaseModel):
    phenotype_id: str
    name: str
    modifier: Optional[str] = None
    modifier_id: Optional[str] = None
    described: bool

    model_config = {"extra": "allow"}

# ------------------------------------------------------------------------------
# Report model (to be embedded in an Individual)
# Here the phenotypes field is a dictionary whose keys are standardized HPO term strings
# and whose values are Phenotype objects.
class Report(BaseModel):
    report_id: int
    reviewed_by: Optional[int] = None  # Reference to a User's user_id
    phenotypes: Dict[str, Phenotype] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

# ------------------------------------------------------------------------------
# IndividualVariant model (per-individual variant info)
# This stores the MongoDB ObjectId (as PyObjectId) of the unique Variant document
# along with the detection_method and segregation for that individual.
class IndividualVariant(BaseModel):
    variant_ref: PyObjectId  # Link to the Variant document _id
    detection_method: Optional[str] = None
    segregation: Optional[str] = None

    model_config = {"extra": "allow"}

# ------------------------------------------------------------------------------
# Individual model (combining base data, embedded reports, and a variant reference)
class Individual(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    individual_id: int
    sex: Optional[str] = None
    age_reported: Optional[str] = None
    cohort: Optional[str] = None
    individual_DOI: Optional[str] = None
    DupCheck: Optional[str] = None
    IndividualIdentifier: Optional[str] = None
    # Force Problematic to be a string (default to empty string if missing)
    Problematic: str = ""
    reports: List[Report] = Field(default_factory=list)
    variant: Optional[IndividualVariant] = None  # Embedded variant info

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }

    @field_validator("Problematic", mode="before")
    @classmethod
    def validate_problematic(cls, v):
        val = none_if_nan(v)
        return val if val is not None else ""

# ------------------------------------------------------------------------------
# Variant Classifications model
class VariantClassifications(BaseModel):
    verdict: Optional[str] = None
    criteria: Optional[str] = None
    comment: Optional[str] = None
    system: Optional[str] = None
    classification_date: Optional[date] = None

    model_config = {"extra": "allow"}

# ------------------------------------------------------------------------------
# Variant Annotations model – detection_method and segregation are removed here.
class VariantAnnotations(BaseModel):
    variant_type: Optional[str] = None
    variant_reported: Optional[str] = None
    ID: Optional[str] = None
    hg19_INFO: Optional[str] = None
    hg19: Optional[str] = None
    hg38_INFO: Optional[str] = None
    hg38: Optional[str] = None
    varsome: Optional[str] = None
    transcript: Optional[str] = None
    c_dot: Optional[str] = None
    p_dot: Optional[str] = None

    model_config = {"extra": "allow"}

# ------------------------------------------------------------------------------
# Variant model (unique across the database)
# Instead of storing a single individual_id, we store a list of individual_ids as MongoDB ObjectIds.
class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    variant_id: int
    individual_ids: List[PyObjectId] = Field(default_factory=list)
    classifications: Optional[VariantClassifications] = None
    annotations: Optional[VariantAnnotations] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }

    @field_validator("annotations", mode="before")
    @classmethod
    def validate_annotations(cls, v):
        if isinstance(v, dict):
            v['ID'] = none_if_nan(v.get('ID'))
            v['hg19_INFO'] = none_if_nan(v.get('hg19_INFO'))
            v['hg38_INFO'] = none_if_nan(v.get('hg38_INFO'))
        return v

# ------------------------------------------------------------------------------
# Publication model
class Publication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    publication_id: int
    publication_alias: str
    publication_type: Optional[str] = None
    publication_entry_date: Optional[date] = None
    PMID: Optional[str] = None
    DOI: Optional[str] = None
    PDF: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    publication_date: Optional[date] = None
    journal_abbreviation: Optional[str] = None
    journal: Optional[str] = None
    keywords: Optional[str] = None
    firstauthor_lastname: Optional[str] = None
    firstauthor_firstname: Optional[str] = None
    update_date: Optional[date] = None
    assignee: Optional[int] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }

    @field_validator("publication_id", mode="before")
    @classmethod
    def validate_publication_id(cls, v):
        if isinstance(v, dict) and "$numberInt" in v:
            return int(v["$numberInt"])
        if isinstance(v, (int, float)):
            return int(v)
        return v

    @field_validator("PMID", mode="before")
    @classmethod
    def validate_pmid(cls, v):
        v = none_if_nan(v)
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @field_validator("DOI", mode="before")
    @classmethod
    def validate_doi(cls, v):
        return none_if_nan(v)

    @field_validator("PDF", mode="before")
    @classmethod
    def validate_pdf(cls, v):
        return none_if_nan(v)

# ------------------------------------------------------------------------------
# Update forward references (for self-referencing embedded models)
Individual.update_forward_refs()
