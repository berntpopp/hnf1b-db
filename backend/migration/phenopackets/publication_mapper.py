"""Publication reference mapping for phenopackets."""

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PublicationMapper:
    """Maps publication IDs to external references."""

    def __init__(self, publications_df: Optional[pd.DataFrame] = None):
        """Initialize publication mapper.

        Args:
            publications_df: DataFrame containing publication data
        """
        self.publication_map = {}
        if publications_df is not None and not publications_df.empty:
            self._build_publication_map(publications_df)

    def _build_publication_map(self, publications_df: pd.DataFrame) -> None:
        """Build publication map from DataFrame.

        Args:
            publications_df: DataFrame containing publication data
        """
        for _, pub_row in publications_df.iterrows():
            # Map by both publication_id and publication_alias
            pub_id = pub_row.get("publication_id")
            pub_alias = pub_row.get("publication_alias")
            if pub_id:
                self.publication_map[str(pub_id)] = pub_row
            if pub_alias:
                self.publication_map[str(pub_alias)] = pub_row

        logger.info(
            f"Created publication map with {len(self.publication_map)} entries"
        )

    def create_publication_reference(
        self, publication_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create an ExternalReference for a publication with PMID and DOI.

        Args:
            publication_id: The publication identifier from the data

        Returns:
            ExternalReference dict with PMID/DOI if available, None otherwise
        """
        if not publication_id or not self.publication_map:
            return None

        pub_data = self.publication_map.get(str(publication_id))
        if pub_data is None:
            return None

        # Convert Series to dict if needed (when pub_data is a pandas Series)
        if hasattr(pub_data, "to_dict"):
            pub_data = pub_data.to_dict()

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
