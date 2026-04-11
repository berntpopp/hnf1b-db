"""Search services sub-package.

Split from the old 513-LOC flat ``search/services.py`` during Wave 4.
The public import path is unchanged::

    from app.search.services import (
        PaginationParams,
        GlobalSearchService,
        PhenopacketSearchService,
        FacetService,
    )

Submodules:

- ``pagination``          — ``PaginationParams`` dataclass
- ``global_search``       — ``GlobalSearchService``
- ``phenopacket_search``  — ``PhenopacketSearchService``
- ``facet``               — ``FacetService``
"""

from .facet import FacetService
from .global_search import GlobalSearchService
from .pagination import PaginationParams
from .phenopacket_search import PhenopacketSearchService

__all__ = [
    "PaginationParams",
    "GlobalSearchService",
    "PhenopacketSearchService",
    "FacetService",
]
