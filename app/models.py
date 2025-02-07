# app/models.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from bson import ObjectId as BsonObjectId  # Provided by PyMongo

# Custom type to represent a MongoDB ObjectId.
class PyObjectId:
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info):
        # If already a PyObjectId, return it.
        if isinstance(v, cls):
            return v
        # If it is a BSON ObjectId, convert it to our type.
        if isinstance(v, BsonObjectId):
            return cls(str(v))
        # If it is a string, assume it's valid.
        if isinstance(v, str):
            return cls(v)
        raise TypeError("Invalid type for PyObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        # In the JSON schema, we want this type to appear as a string.
        return {"type": "string"}

    def __init__(self, oid: str):
        self.oid = oid

    def __str__(self):
        return self.oid

    def __repr__(self):
        return f"PyObjectId({self.oid})"


# Now update each model to include a json encoder for our custom type.
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
    publication_entry_date: date
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

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {PyObjectId: lambda v: str(v)}
    }


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
