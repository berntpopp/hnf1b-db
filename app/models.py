# app/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
import math
from bson import ObjectId as BsonObjectId  # Provided by PyMongo

# Utility function to treat NaN values as None.
def none_if_nan(v):
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    if isinstance(v, dict) and "$numberDouble" in v:
        try:
            val = float(v["$numberDouble"])
            if math.isnan(val):
                return None
            return str(val) if val.is_integer() else str(val)
        except Exception:
            return None
    return v

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
        # Represent this type as a string in JSON schema.
        return {"type": "string"}

    def __init__(self, oid: str):
        self.oid = oid

    def __str__(self):
        return self.oid

    def __repr__(self):
        return f"PyObjectId({self.oid})"


# ------------------------------
# User model (for reviewers/users)
# ------------------------------
class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: int
    user_name: str
    password: str
    email: str
    user_role: str
    first_name: str
    family_name: str
    orcid: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# ------------------------------
# Individual model
# ------------------------------
class Individual(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    individual_id: int
    sex: Optional[str] = Field(default=None)
    age_reported: Optional[str] = Field(default=None)  # New field for age reported
    cohort: Optional[str] = Field(default=None)        # New field for cohort (e.g., "born" vs. "fetus")
    individual_DOI: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# ------------------------------
# Phenotype sub-model for Reports
# ------------------------------
class Phenotype(BaseModel):
    phenotype_id: str
    name: str
    modifier: Optional[str] = None
    described: bool

    model_config = {
        "extra": "allow"
    }


# ------------------------------
# Report model
# ------------------------------
class Report(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    report_id: int
    individual_id: int
    report_date: Optional[date] = Field(default=None)
    report_review_date: Optional[date] = Field(default=None)
    reviewed_by: Optional[int] = Field(default=None)  # Reference to a User's user_id
    phenotypes: Optional[List[Phenotype]] = Field(default=[])

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# ------------------------------
# Variant sub-models for nested data
# ------------------------------
class VariantClassifications(BaseModel):
    verdict: Optional[str] = None
    criteria: Optional[str] = None
    comment: Optional[str] = None
    system: Optional[str] = None
    classification_date: Optional[date] = None

    model_config = {"extra": "allow"}


class VariantAnnotations(BaseModel):
    variant_type: Optional[str] = None
    variant_reported: Optional[str] = None
    ID: Optional[str] = None
    hg19_INFO: Optional[str] = None
    hg19: Optional[str] = None
    hg38_INFO: Optional[str] = None
    hg38: Optional[str] = None
    varsome: Optional[str] = None
    detection_method: Optional[str] = None
    segregation: Optional[str] = None

    model_config = {"extra": "allow"}


# ------------------------------
# Variant model
# ------------------------------
class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    variant_id: int
    individual_id: int
    is_current: bool
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
        # If annotations is a dict, apply none_if_nan to certain fields.
        if isinstance(v, dict):
            v['ID'] = none_if_nan(v.get('ID'))
            v['hg19_INFO'] = none_if_nan(v.get('hg19_INFO'))
            v['hg38_INFO'] = none_if_nan(v.get('hg38_INFO'))
        return v


# ------------------------------
# Publication model
# ------------------------------
class Publication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    publication_id: int
    publication_alias: str
    publication_type: Optional[str] = Field(default=None)
    publication_entry_date: Optional[date] = Field(default=None)
    PMID: Optional[str] = Field(default=None)
    DOI: Optional[str] = Field(default=None)
    PDF: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    publication_date: Optional[date] = Field(default=None)
    journal_abbreviation: Optional[str] = Field(default=None)
    journal: Optional[str] = Field(default=None)
    keywords: Optional[str] = Field(default=None)
    firstauthor_lastname: Optional[str] = Field(default=None)
    firstauthor_firstname: Optional[str] = Field(default=None)
    update_date: Optional[date] = Field(default=None)
    PDF_drive_link: Optional[str] = Field(default=None)
    assignee: Optional[int] = Field(default=None)
    IndividualsReviewed: Optional[int] = Field(default=None)
    Comment: Optional[str] = Field(default=None)

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
