"""Publication reference mapping for phenopackets."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from migration.phenopackets.base_mapper import SheetMapper

logger = logging.getLogger(__name__)


class PublicationMapper(SheetMapper):
    """Maps publication IDs to external references.

    Extends SheetMapper to provide publication-specific functionality
    for creating ExternalReference objects with PMID/DOI metadata.
    """

    def _get_map_name(self) -> str:
        """Get human-readable name for logging.

        Returns:
            "publication"
        """
        return "publication"

    def _get_key_columns(self) -> List[str]:
        """Get columns to use as lookup keys.

        Publications are indexed by both publication_id and publication_alias
        to support lookup by either identifier.

        Returns:
            ["publication_id", "publication_alias"]
        """
        return ["publication_id", "publication_alias"]

    def create_publication_reference(
        self, publication_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create an ExternalReference for a publication with PMID and DOI.

        Args:
            publication_id: The publication identifier from the data

        Returns:
            ExternalReference dict with PMID/DOI if available, None otherwise
        """
        if not publication_id or not self:
            return None

        # Use base class method for lookup
        pub_data = self.get_as_dict(publication_id)
        if pub_data is None:
            return None

        # Build proper ExternalReference with PMID/DOI
        external_ref = {}

        # Check for PMID
        pmid = pub_data.get("PMID")
        if pmid and pd.notna(pmid):
            # Clean PMID (remove any prefixes and handle float)
            pmid_clean = (
                str(int(float(pmid)))
                if isinstance(pmid, (float, np.floating))
                else str(pmid)
            )
            pmid_clean = pmid_clean.replace("PMID:", "").strip()
            if pmid_clean.isdigit():
                external_ref["id"] = f"PMID:{pmid_clean}"
                external_ref["reference"] = (
                    f"https://pubmed.ncbi.nlm.nih.gov/{pmid_clean}"
                )

        # Check for DOI
        doi = pub_data.get("DOI")
        if doi and pd.notna(doi) and not external_ref.get("id"):
            # Use DOI if PMID is not available
            doi_clean = str(doi).strip()
            if doi_clean.startswith("10."):
                external_ref["id"] = f"DOI:{doi_clean}"
                external_ref["reference"] = f"https://doi.org/{doi_clean}"
        elif doi and pd.notna(doi) and external_ref.get("id"):
            # If we have both PMID and DOI, add DOI to description (minimal format)
            doi_clean = str(doi).strip()
            if doi_clean.startswith("10."):
                external_ref["description"] = f"DOI:{doi_clean}"

        # If we still don't have a proper PMID or DOI, check for special cases
        if not external_ref.get("id"):
            # Handle special case for internal/unpublished data
            if publication_id == "our_report":
                return {
                    "id": "INTERNAL:our_report",
                    "description": "Unpublished internal case series",
                }
            # For other cases without PMID/DOI, return None
            return None

        return external_ref
