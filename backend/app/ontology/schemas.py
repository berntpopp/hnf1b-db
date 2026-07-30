"""Response models for ontology and controlled-vocabulary endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field


class VocabularyItem(BaseModel):
    """One controlled-vocabulary member.

    The canonical shape for vocabularies added by the curation storage contract.
    Pre-existing endpoints (sex, interpretation-status, allelic-state,
    evidence-code) have divergent shapes and are deliberately left alone.
    """

    value: str = Field(..., description="Stored token, e.g. 'mlpa'")
    label: str = Field(..., description="Curator-facing label, e.g. 'MLPA'")
    description: Optional[str] = Field(None, description="Optional clarifying text")


class VocabularyResponse(BaseModel):
    """Envelope matching every other vocabulary endpoint in this API."""

    data: List[VocabularyItem]
