"""HPO term mapping for phenotypic features."""

import logging
from typing import Any, Dict, Optional

import pandas as pd

from migration.phenopackets.ontology_mapper import OntologyMapper

logger = logging.getLogger(__name__)


class HPOMapper(OntologyMapper):
    """Maps phenotype categories to HPO terms.

    Implements OntologyMapper interface following Dependency Inversion Principle.
    High-level modules depend on this abstraction, not this concrete implementation.
    """

    def __init__(self, mappings: Optional[Dict[str, Dict[str, str]]] = None):
        """Initialize with default or provided HPO mappings.

        Args:
            mappings: Optional pre-configured mappings. If None, uses defaults.
        """
        self.hpo_mappings = mappings if mappings else self._init_default_hpo_mappings()

    def _init_default_hpo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize default HPO term mappings for phenotypes."""
        return {
            # Kidney phenotypes
            "renalinsufficancy": {"id": "HP:0000083", "label": "Renal insufficiency"},
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
        """Build HPO mappings from Phenotype sheet.

        Args:
            phenotypes_df: DataFrame containing phenotype mappings
        """
        if phenotypes_df is None or phenotypes_df.empty:
            logger.warning("No phenotype dataframe provided, using default mappings")
            return

        self.hpo_mappings = {}
        for _, row in phenotypes_df.iterrows():
            category = row.get("phenotype_category")
            hpo_id = row.get("phenotype_id")
            hpo_label = row.get("phenotype_name")

            if pd.notna(category) and pd.notna(hpo_id):
                # Normalize the category name to match column names in individuals sheet
                normalized_category = self._normalize_column_name(category)
                self.hpo_mappings[normalized_category] = {
                    "id": hpo_id,
                    "label": hpo_label if pd.notna(hpo_label) else category,
                }

        logger.info(f"Built HPO mappings for {len(self.hpo_mappings)} phenotypes")
        logger.info(f"Phenotype categories: {list(self.hpo_mappings.keys())[:10]}...")

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