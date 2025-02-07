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
        # Represent this type as a string in the JSON schema.
        return {"type": "string"}

    def __init__(self, oid: str):
        self.oid = oid

    def __str__(self):
        return self.oid

    def __repr__(self):
        return f"PyObjectId({self.oid})"


# User model (for reviewers/users imported from the Reviewers sheet)
class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
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
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }


class Individual(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    individual_id: int
    sex: Optional[str]
    individual_DOI: Optional[str] = None

    model_config = {
        "from_attributes": True,        # formerly orm_mode
        "populate_by_name": True,         # formerly allow_population_by_field_name
        "arbitrary_types_allowed": True,  # allow our custom type
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }


class Report(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    report_id: int
    report_date: date
    report_review_date: date
    individual_id: int
    reported_multiple: bool
    cohort: Optional[str] = None
    onset_age: Optional[str] = None
    report_age: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }


class Publication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    publication_id: int
    publication_alias: str
    publication_type: Optional[str] = None
    # Make entry date optional because some records may not include it.
    publication_entry_date: Optional[date] = None
    PMID: Optional[str] = None
    DOI: Optional[str] = None
    PDF: Optional[str] = None
    # New fields from migration:
    PDF_drive_link: Optional[str] = None
    Assigne: Optional[str] = None
    IndividualsReviewed: Optional[int] = None
    Comment: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }

    @field_validator("PMID", mode="before")
    @classmethod
    def validate_pmid(cls, v):
        """
        Convert numeric PMID values to strings.
        If v is a float or int, convert to string.
        If v is NaN, return None.
        """
        if v is None:
            return None
        if isinstance(v, float):
            if math.isnan(v):
                return None
            # If the float represents an integer, return it as int string.
            if v.is_integer():
                return str(int(v))
            return str(v)
        if isinstance(v, int):
            return str(v)
        return v


class Variant(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    variant_id: int
    variant_report_status: int
    variant_annotation_source: Optional[str] = None
    variant_annotation_date: Optional[date] = None
    variant_type: Optional[str] = None
    variant_vcf_hg19: Optional[str] = None
    ID: Optional[str] = None
    INFO: Optional[str] = None
    transcript: Optional[str] = None
    c_dot: Optional[str] = None
    p_dot: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }
