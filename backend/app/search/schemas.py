from typing import List, Optional, Dict
from pydantic import BaseModel

class SearchResultItem(BaseModel):
    id: str
    label: str
    type: str
    subtype: Optional[str] = None
    extra_info: Optional[str] = None
    score: Optional[float] = None

class AutocompleteResponse(BaseModel):
    results: List[SearchResultItem]

class GlobalSearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
    page: int
    page_size: int
    summary: Dict[str, int]
