"""Data sanitization and normalization for phenopackets."""

from typing import Any, Dict


class PhenopacketSanitizer:
    """Sanitize and clean phenopacket data."""

    @staticmethod
    def sanitize_phenopacket(phenopacket: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize a phenopacket document.

        Removes null values and empty arrays/objects recursively.

        Args:
            phenopacket: The phenopacket to sanitize

        Returns:
            Sanitized phenopacket
        """

        def remove_nulls(obj):
            if isinstance(obj, dict):
                return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [remove_nulls(item) for item in obj if item is not None]
            return obj

        def remove_empty(obj):
            if isinstance(obj, dict):
                cleaned = {k: remove_empty(v) for k, v in obj.items()}
                return {k: v for k, v in cleaned.items() if v not in [[], {}, None]}
            elif isinstance(obj, list):
                return [remove_empty(item) for item in obj]
            return obj

        phenopacket = remove_nulls(phenopacket)
        phenopacket = remove_empty(phenopacket)

        return phenopacket

    @staticmethod
    def normalize_ontology_term(term: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize an ontology term.

        Ensures ontology term IDs are uppercase for standard ontologies.

        Args:
            term: Ontology term to normalize

        Returns:
            Normalized ontology term
        """
        if not isinstance(term, dict):
            return term

        # Ensure ID is uppercase for standard ontologies
        if "id" in term and isinstance(term["id"], str):
            parts = term["id"].split(":")
            if len(parts) == 2 and parts[0].upper() in ["HP", "MONDO", "OMIM", "LOINC"]:
                term["id"] = f"{parts[0].upper()}:{parts[1]}"

        return term
