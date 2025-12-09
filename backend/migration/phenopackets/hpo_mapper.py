"""HPO term mapping for phenotypic features with canonical label normalization."""

import logging
from typing import Dict, Optional

import pandas as pd

from migration.phenopackets.ontology_mapper import OntologyMapper

logger = logging.getLogger(__name__)


class HPOMapper(OntologyMapper):
    """Maps phenotype categories to HPO terms with canonical label normalization.

    Implements OntologyMapper interface following Dependency Inversion Principle.
    High-level modules depend on this abstraction, not this concrete implementation.

    Label Normalization:
        When normalize_labels=True (default), the mapper fetches canonical labels
        from the HPO API via HybridOntologyService. This ensures consistent labels
        across all phenopackets, avoiding issues like HP:0012622 appearing as both
        "Chronic kidney disease" and "chronic kidney disease, not specified".
    """

    def __init__(
        self,
        mappings: Optional[Dict[str, Dict[str, str]]] = None,
        normalize_labels: bool = True,
    ):
        """Initialize with default or provided HPO mappings.

        Args:
            mappings: Optional pre-configured mappings. If None, uses defaults.
            normalize_labels: If True, fetch canonical labels from HPO API.
                            Defaults to True for data quality.
        """
        self.normalize_labels = normalize_labels
        self._canonical_labels: Dict[str, str] = {}
        self._ontology_service = None  # Lazy-loaded to avoid circular imports
        self.hpo_mappings = mappings if mappings else self._init_default_hpo_mappings()

    def _get_ontology_service(self):
        """Lazy-load ontology service to avoid circular imports."""
        if self._ontology_service is None:
            try:
                from app.services.ontology_service import ontology_service

                self._ontology_service = ontology_service
            except ImportError:
                logger.warning(
                    "Could not import ontology_service - canonical label "
                    "normalization disabled"
                )
                self.normalize_labels = False
        return self._ontology_service

    def _get_canonical_label(self, hpo_id: str, fallback_label: str) -> str:
        """Get canonical HPO label from API or local cache.

        Uses HybridOntologyService which has multi-level caching:
        1. Memory cache (instant)
        2. File cache (fast)
        3. HPO JAX API (authoritative)
        4. OLS API (backup)
        5. Local fallback (last resort)

        Args:
            hpo_id: HPO term ID (e.g., "HP:0012622")
            fallback_label: Label to use if lookup fails

        Returns:
            Canonical label from HPO or fallback
        """
        if not self.normalize_labels:
            return fallback_label

        # Check internal cache first (faster than service lookup)
        if hpo_id in self._canonical_labels:
            return self._canonical_labels[hpo_id]

        try:
            service = self._get_ontology_service()
            if service is None:
                self._canonical_labels[hpo_id] = fallback_label
                return fallback_label

            term = service.get_term(hpo_id)

            # Only use API label if it's valid (not "Unknown term:")
            if term and not term.label.startswith("Unknown term:"):
                self._canonical_labels[hpo_id] = term.label
                return term.label

        except Exception as e:
            logger.debug(f"Failed to lookup canonical label for {hpo_id}: {e}")

        # Cache fallback to avoid repeated failures
        self._canonical_labels[hpo_id] = fallback_label
        return fallback_label

    def _init_default_hpo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize default HPO term mappings for phenotypes.

        These are canonical labels from the HPO ontology.
        """
        return {
            # Kidney phenotypes
            "chronic kidney disease": {
                "id": "HP:0012622",
                "label": "Chronic kidney disease",
            },
            "stage 1 chronic kidney disease": {
                "id": "HP:0012623",
                "label": "Stage 1 chronic kidney disease",
            },
            "stage 2 chronic kidney disease": {
                "id": "HP:0012624",
                "label": "Stage 2 chronic kidney disease",
            },
            "stage 3 chronic kidney disease": {
                "id": "HP:0012625",
                "label": "Stage 3 chronic kidney disease",
            },
            "stage 4 chronic kidney disease": {
                "id": "HP:0012626",
                "label": "Stage 4 chronic kidney disease",
            },
            "stage 5 chronic kidney disease": {
                "id": "HP:0003774",
                "label": "Stage 5 chronic kidney disease",
            },
            "renalcysts": {"id": "HP:0000107", "label": "Renal cyst"},
            "renalhypoplasia": {"id": "HP:0000089", "label": "Renal hypoplasia"},
            "solitarykidney": {
                "id": "HP:0004729",
                "label": "Solitary functioning kidney",
            },
            "multicysticdysplastickidney": {
                "id": "HP:0000003",
                "label": "Multicystic kidney dysplasia",
            },
            "hyperechogenicity": {
                "id": "HP:0010935",
                "label": "Increased echogenicity of kidneys",
            },
            "urinarytractmalformation": {
                "id": "HP:0000079",
                "label": "Abnormality of the urinary system",
            },
            "antenatalrenalabnormalities": {
                "id": "HP:0010945",
                "label": "Fetal renal anomaly",
            },
            "multiple glomerular cysts": {
                "id": "HP:0100611",
                "label": "Multiple glomerular cysts",
            },
            "oligomeganephronia": {"id": "HP:0004719", "label": "Oligomeganephronia"},
            # Metabolic phenotypes
            "hypomagnesemia": {"id": "HP:0002917", "label": "Hypomagnesemia"},
            "hyperuricemia": {"id": "HP:0002149", "label": "Hyperuricemia"},
            "gout": {"id": "HP:0001997", "label": "Gout"},
            "hypokalemia": {"id": "HP:0002900", "label": "Hypokalemia"},
            "hyperparathyroidism": {"id": "HP:0000843", "label": "Hyperparathyroidism"},
            # Diabetes/Pancreas
            "mody": {
                "id": "HP:0004904",
                "label": "Maturity-onset diabetes of the young",
            },
            "pancreatichypoplasia": {
                "id": "HP:0100575",
                "label": "Pancreatic hypoplasia",
            },
            "exocrinepancreaticinsufficiency": {
                "id": "HP:0001738",
                "label": "Exocrine pancreatic insufficiency",
            },
            # Liver
            "abnormalliverphysiology": {
                "id": "HP:0031865",
                "label": "Abnormal liver physiology",
            },
            "elevatedhepatictransaminase": {
                "id": "HP:0002910",
                "label": "Elevated hepatic transaminase",
            },
            # Genital
            "genitaltractabnormality": {
                "id": "HP:0000078",
                "label": "Abnormality of the genital system",
            },
            # Developmental
            "neurodevelopmentaldisorder": {
                "id": "HP:0012759",
                "label": "Neurodevelopmental abnormality",
            },
            "mentaldisease": {
                "id": "HP:0000708",
                "label": "Behavioral abnormality",
            },
            "dysmorphicfeatures": {
                "id": "HP:0001999",
                "label": "Abnormal facial shape",
            },
            "shortstature": {"id": "HP:0004322", "label": "Short stature"},
            "prematurebirth": {"id": "HP:0001622", "label": "Premature birth"},
            # Neurological
            "brainabnormality": {
                "id": "HP:0012443",
                "label": "Abnormality of brain morphology",
            },
            "seizures": {"id": "HP:0001250", "label": "Seizures"},
            # Other systems
            "eyeabnormality": {"id": "HP:0000478", "label": "Abnormality of the eye"},
            "congenitalcardiacanomalies": {
                "id": "HP:0001627",
                "label": "Abnormal heart morphology",
            },
            "musculoskeletalfeatures": {
                "id": "HP:0033127",
                "label": "Abnormality of the musculoskeletal system",
            },
        }

    def build_from_dataframe(self, phenotypes_df: pd.DataFrame) -> None:
        """Build HPO mappings from Phenotype sheet with canonical label normalization.

        Args:
            phenotypes_df: DataFrame containing phenotype mappings
        """
        if phenotypes_df is None or phenotypes_df.empty:
            logger.warning("No phenotype dataframe provided, using default mappings")
            return

        self.hpo_mappings = {}
        normalized_count = 0

        for _, row in phenotypes_df.iterrows():
            category = row.get("phenotype_category")
            hpo_id = row.get("phenotype_id")
            source_label = row.get("phenotype_name")

            if pd.notna(category) and pd.notna(hpo_id):
                # Get canonical label (normalizes to official HPO label)
                fallback = source_label if pd.notna(source_label) else category
                canonical_label = self._get_canonical_label(hpo_id, fallback)

                # Track normalization for logging
                if pd.notna(source_label) and canonical_label != source_label:
                    logger.debug(
                        f"Normalized label for {hpo_id}: "
                        f"'{source_label}' -> '{canonical_label}'"
                    )
                    normalized_count += 1

                # Normalize the category name to match column names in individuals sheet
                normalized_category = self._normalize_column_name(category)
                self.hpo_mappings[normalized_category] = {
                    "id": hpo_id,
                    "label": canonical_label,
                }

                # ALSO add mapping for the phenotype_name
                # This allows cell values like "Stage 1" to be looked up
                if pd.notna(source_label):
                    normalized_label = self._normalize_column_name(source_label)
                    self.hpo_mappings[normalized_label] = {
                        "id": hpo_id,
                        "label": canonical_label,
                    }

        logger.info(f"Built HPO mappings for {len(self.hpo_mappings)} phenotypes")
        if normalized_count > 0:
            logger.info(f"Normalized {normalized_count} HPO labels to canonical form")

    def normalize_key(self, key: str) -> str:
        """Normalize a phenotype key for lookup.

        Args:
            key: Raw phenotype key

        Returns:
            Normalized key (lowercase, no spaces or underscores)
        """
        if pd.isna(key):
            return ""
        return str(key).strip().lower().replace(" ", "").replace("_", "")

    def _normalize_column_name(self, name: str) -> str:
        """Normalize column names to lowercase without spaces.

        Deprecated: Use normalize_key() instead (part of OntologyMapper interface).
        """
        return self.normalize_key(name)

    def get_hpo_term(self, phenotype_key: str) -> Optional[Dict[str, str]]:
        """Get HPO term for a phenotype key.

        Args:
            phenotype_key: Normalized phenotype key

        Returns:
            Dictionary with 'id' and 'label' or None if not found
        """
        return self.hpo_mappings.get(phenotype_key)

    def get_all_mappings(self) -> Dict[str, Dict[str, str]]:
        """Get all HPO mappings.

        Returns:
            Dictionary of all mappings
        """
        return self.hpo_mappings
