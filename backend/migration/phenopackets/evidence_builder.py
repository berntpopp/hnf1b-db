"""Evidence builder for phenotypic features and variants.

DRY Principle: Single source of truth for evidence building across the migration system.
"""

from typing import Any, Dict, List, Optional

from migration.phenopackets.publication_mapper import PublicationMapper


class EvidenceBuilder:
    """Build evidence items with publication references and timestamps.

    This class eliminates code duplication by providing a single reusable method
    for building evidence structures, replacing multiple duplicated 30-line blocks
    throughout the codebase.

    Follows DRY (Don't Repeat Yourself) principle - single source of truth.
    """

    def __init__(self, publication_mapper: Optional[PublicationMapper] = None):
        """Initialize evidence builder.

        Args:
            publication_mapper: Optional publication reference mapper for PMID/DOI resolution
        """
        self.publication_mapper = publication_mapper

    def build_evidence(
        self,
        publication_id: Optional[str] = None,
        review_timestamp: Optional[str] = None,
        evidence_code: str = "ECO:0000033",
        evidence_label: str = "author statement",
    ) -> List[Dict[str, Any]]:
        """Build evidence list for a phenotypic feature or variant.

        This method replaces 4+ duplicated code blocks (30+ lines each) with a single
        reusable implementation following the DRY principle.

        Args:
            publication_id: Publication identifier (PMID or DOI)
            review_timestamp: ISO8601 timestamp when evidence was recorded
            evidence_code: ECO (Evidence & Conclusion Ontology) code (default: ECO:0000033)
            evidence_label: Human-readable evidence label (default: "author statement")

        Returns:
            List of evidence dictionaries in GA4GH Phenopackets v2 format

        Examples:
            >>> builder = EvidenceBuilder(publication_mapper)
            >>> evidence = builder.build_evidence(
            ...     publication_id="PMID:12345678",
            ...     review_timestamp="2024-01-15T10:30:00Z"
            ... )
            >>> evidence
            [{'evidenceCode': {'id': 'ECO:0000033', 'label': 'author statement'},
              'reference': {'id': 'PMID:12345678', 'description': '...',
                           'recordedAt': '2024-01-15T10:30:00Z'}}]
        """
        evidence = []

        # Build evidence item with publication reference
        if publication_id:
            evidence_item = {
                "evidenceCode": {"id": evidence_code, "label": evidence_label},
            }

            # Try to resolve publication via mapper
            if self.publication_mapper:
                pub_ref = self.publication_mapper.create_publication_reference(
                    str(publication_id)
                )
                if pub_ref:
                    evidence_item["reference"] = pub_ref
                    if review_timestamp:
                        evidence_item["reference"]["recordedAt"] = review_timestamp
                elif review_timestamp:
                    # Mapper didn't resolve, but we have timestamp
                    evidence_item["reference"] = {"recordedAt": review_timestamp}
            elif review_timestamp:
                # No mapper, just timestamp
                evidence_item["reference"] = {"recordedAt": review_timestamp}

            evidence.append(evidence_item)

        # Build evidence item with only timestamp (no publication)
        elif review_timestamp:
            evidence.append(
                {
                    "evidenceCode": {"id": evidence_code, "label": evidence_label},
                    "reference": {
                        "description": "Clinical observation",
                        "recordedAt": review_timestamp,
                    },
                }
            )

        return evidence
