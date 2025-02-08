# app/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date
import math
from bson import ObjectId as BsonObjectId  # Provided by PyMongo

# Custom type to represent a MongoDB ObjectId.
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
    orcid: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# Individual model
class Individual(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    individual_id: int
    sex: Optional[str] = Field(default=None)
    individual_DOI: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# Report model
class Report(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    report_id: int
    report_date: date
    report_review_date: date
    individual_id: int
    reported_multiple: bool
    cohort: Optional[str] = Field(default=None)
    onset_age: Optional[str] = Field(default=None)
    report_age: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }


# Publication model – note that publication_entry_date is now optional.
class Publication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    publication_id: int
    publication_alias: str
    publication_type: Optional[str] = Field(default=None)
    publication_entry_date: Optional[date] = Field(default=None)  # Made optional
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
    # New fields from migration:
    PDF_drive_link: Optional[str] = Field(default=None)
    Assigne: Optional[str] = Field(default=None)
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
        # Convert numeric PMID values to strings (and treat NaN as None)
        if v is None:
            return None
        try:
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        if isinstance(v, (int, float)):
            return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        return v

    @field_validator("DOI", mode="before")
    @classmethod
    def validate_doi(cls, v):
        return v  # You can add additional cleaning if necessary

    @field_validator("PDF", mode="before")
    @classmethod
    def validate_pdf(cls, v):
        return v  # Add cleaning as needed

    @field_validator("IndividualsReviewed", mode="before")
    @classmethod
    def validate_individuals_reviewed(cls, v):
        try:
            if isinstance(v, dict) and "$numberDouble" in v:
                val = float(v["$numberDouble"])
                return int(val) if val.is_integer() else val
            if isinstance(v, (int, float)):
                if isinstance(v, float) and math.isnan(v):
                    return None
                return int(v) if isinstance(v, float) and v.is_integer() else v
        except Exception:
            return None
        return v

    @field_validator("Comment", mode="before")
    @classmethod
    def validate_comment(cls, v):
        if isinstance(v, str) and v.lower() == "nan":
            return None
        return v


# Variant model
class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    variant_id: int
    variant_report_status: int
    variant_annotation_source: Optional[str] = Field(default=None)
    variant_annotation_date: Optional[date] = Field(default=None)
    variant_type: Optional[str] = Field(default=None)
    variant_vcf_hg19: Optional[str] = Field(default=None)
    ID: Optional[str] = Field(default=None)
    INFO: Optional[str] = Field(default=None)
    transcript: Optional[str] = Field(default=None)
    c_dot: Optional[str] = Field(default=None)
    p_dot: Optional[str] = Field(default=None)

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)},
        "extra": "allow"
    }
