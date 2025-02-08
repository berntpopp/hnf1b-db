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
    if isinstance(v, str) and v.lower() == "nan":
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
        # In JSON, we want to represent this type as a string.
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
    age_reported: Optional[str] = Field(default=None)
    cohort: Optional[str] = Field(default=None)
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


# ------------------------------
# Report model
# ------------------------------
class Report(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    report_id: int
    individual_id: int
    report_date: date
    report_review_date: date
    reviewed_by: Optional[int] = Field(default=None)
    phenotypes: Optional[List[Phenotype]] = Field(default=[])

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# ------------------------------
# Variant model
# ------------------------------
class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    variant_id: int
    individual_id: int
    is_current: bool
    # Classifications:
    verdict_classification: Optional[str] = Field(default=None)
    criteria_classification: Optional[str] = Field(default=None)
    comment_classification: Optional[str] = Field(default=None)
    system_classification: Optional[str] = Field(default=None)
    date_classification: Optional[date] = Field(default=None)
    # Annotations:
    variant_type: Optional[str] = Field(default=None)
    variant_reported: Optional[str] = Field(default=None)
    ID: Optional[str] = Field(default=None)
    hg19_INFO: Optional[str] = Field(default=None)
    hg19: Optional[str] = Field(default=None)
    hg38_INFO: Optional[str] = Field(default=None)
    hg38: Optional[str] = Field(default=None)
    varsome: Optional[str] = Field(default=None)
    detection_method: Optional[str] = Field(default=None)
    segregation: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }

    @field_validator("ID", mode="before")
    @classmethod
    def validate_id_field(cls, v):
        return none_if_nan(v)

    @field_validator("hg19_INFO", mode="before")
    @classmethod
    def validate_hg19_info(cls, v):
        return none_if_nan(v)

    @field_validator("hg38_INFO", mode="before")
    @classmethod
    def validate_hg38_info(cls, v):
        return none_if_nan(v)


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
    # New fields:
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
