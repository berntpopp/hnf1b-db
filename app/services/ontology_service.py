"""Hybrid ontology service for phenopackets - uses APIs with local fallback."""

import json
import os
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from pydantic import BaseModel

# Import existing hardcoded mappings
from migration.modules.phenotypes import KIDNEY_BIOPSY_MAPPING, RENAL_MAPPING


class OntologySource(Enum):
    """Source of ontology data."""

    HPO_API = "hpo_api"
    OLS_API = "ols_api"
    MONARCH_API = "monarch_api"
    LOCAL_HARDCODED = "local_hardcoded"
    LOCAL_CACHE = "local_cache"


class OntologyTerm(BaseModel):
    """Standardized ontology term representation."""

    id: str
    label: str
    description: Optional[str] = None
    synonyms: List[str] = []
    parents: List[str] = []
    source: OntologySource = OntologySource.LOCAL_HARDCODED
    fetched_at: Optional[datetime] = None
    is_obsolete: bool = False


class OntologyAPIClient:
    """Base class for ontology API clients."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.session = requests.Session()

    def get_term(self, term_id: str) -> Optional[OntologyTerm]:
        """Get term from API - to be implemented by subclasses."""
        raise NotImplementedError


class HPOAPIClient(OntologyAPIClient):
    """Client for HPO JAX API."""

    BASE_URL = "https://hpo.jax.org/api/hpo"

    def get_term(self, term_id: str) -> Optional[OntologyTerm]:
        """Fetch HPO term from API."""
        if not term_id.startswith("HP:"):
            return None

        try:
            url = f"{self.BASE_URL}/term/{term_id}"
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                details = data.get("details", {})

                return OntologyTerm(
                    id=term_id,
                    label=details.get("name", ""),
                    description=details.get("definition", ""),
                    synonyms=details.get("synonyms", []),
                    parents=[
                        p["ontologyId"]
                        for p in data.get("relations", {}).get("parents", [])
                    ],
                    source=OntologySource.HPO_API,
                    fetched_at=datetime.now(),
                )
        except Exception as e:
            print(f"Error fetching HPO term {term_id}: {e}")

        return None


class OLSAPIClient(OntologyAPIClient):
    """Client for EBI's Ontology Lookup Service."""

    BASE_URL = "https://www.ebi.ac.uk/ols4/api"

    def get_term(self, term_id: str) -> Optional[OntologyTerm]:
        """Fetch term from OLS API (supports HPO, MONDO, etc.)."""
        try:
            # Determine ontology from prefix
            if term_id.startswith("HP:"):
                ontology = "hp"
            elif term_id.startswith("MONDO:"):
                ontology = "mondo"
            elif term_id.startswith("ORPHA:"):
                ontology = "ordo"  # Orphanet in OLS
            else:
                return None

            # OLS uses underscore instead of colon in the term ID part
            iri_id = term_id.replace(":", "_")
            # Construct the full IRI and properly encode it
            iri = f"http://purl.obolibrary.org/obo/{iri_id}"
            # Double encode the IRI as required by OLS API (encodes the already-encoded URL parameter)
            encoded_iri = quote(quote(iri, safe=''), safe='')
            url = f"{self.BASE_URL}/ontologies/{ontology}/terms/{encoded_iri}"

            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                return OntologyTerm(
                    id=term_id,
                    label=data.get("label", ""),
                    description=data.get("description", [""])[0]
                    if data.get("description")
                    else "",
                    synonyms=data.get("synonyms", []),
                    source=OntologySource.OLS_API,
                    fetched_at=datetime.now(),
                    is_obsolete=data.get("is_obsolete", False),
                )
        except Exception as e:
            print(f"Error fetching term {term_id} from OLS: {e}")

        return None


class MonarchAPIClient(OntologyAPIClient):
    """Client for Monarch Initiative API."""

    BASE_URL = "https://api.monarchinitiative.org/v3"

    def get_term(self, term_id: str) -> Optional[OntologyTerm]:
        """Fetch term from Monarch API."""
        try:
            url = f"{self.BASE_URL}/entity/{term_id}"
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                return OntologyTerm(
                    id=term_id,
                    label=data.get("name", ""),
                    description=data.get("description", ""),
                    synonyms=data.get("synonyms", []),
                    source=OntologySource.MONARCH_API,
                    fetched_at=datetime.now(),
                )
        except Exception as e:
            print(f"Error fetching term {term_id} from Monarch: {e}")

        return None


class LocalMappingsProvider:
    """Provider for existing hardcoded mappings."""

    def __init__(self):
        self.mappings = self._build_mappings()

    def _build_mappings(self) -> Dict[str, OntologyTerm]:
        """Build mappings from existing hardcoded data."""
        mappings = {}

        # Add renal mappings
        for key, value in RENAL_MAPPING.items():
            term_id = value["phenotype_id"]
            if term_id not in mappings:
                mappings[term_id] = OntologyTerm(
                    id=term_id,
                    label=value["name"],
                    source=OntologySource.LOCAL_HARDCODED,
                )

        # Add kidney biopsy mappings
        for category_mappings in KIDNEY_BIOPSY_MAPPING.values():
            for term_id, details in category_mappings.items():
                if term_id not in mappings:
                    mappings[term_id] = OntologyTerm(
                        id=details["phenotype_id"],
                        label=details["name"],
                        source=OntologySource.LOCAL_HARDCODED,
                    )

        # Add additional common HNF1B-related terms
        additional_terms = {
            "HP:0000083": "Renal insufficiency",
            "HP:0000107": "Renal cyst",
            "HP:0000003": "Multicystic kidney dysplasia",
            "HP:0000078": "Genital abnormality",
            "HP:0000819": "Diabetes mellitus",
            "HP:0002917": "Hypomagnesemia",
            "HP:0002900": "Hypokalemia",
            "HP:0003149": "Hyperuricemia",
            "HP:0001997": "Gout",
            "MONDO:0005147": "Type 2 diabetes mellitus",
            "MONDO:0018874": "HNF1B-related autosomal dominant tubulointerstitial kidney disease",
        }

        for term_id, label in additional_terms.items():
            if term_id not in mappings:
                mappings[term_id] = OntologyTerm(
                    id=term_id, label=label, source=OntologySource.LOCAL_HARDCODED
                )

        return mappings

    def get_term(self, term_id: str) -> Optional[OntologyTerm]:
        """Get term from local mappings."""
        return self.mappings.get(term_id)


class FileCache:
    """Simple file-based cache for API responses."""

    def __init__(self, cache_dir: str = ".ontology_cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _get_cache_path(self, term_id: str) -> Path:
        """Get cache file path for a term."""
        # Replace special characters for filesystem
        safe_id = term_id.replace(":", "_").replace("/", "_")
        return self.cache_dir / f"{safe_id}.json"

    def get(self, term_id: str) -> Optional[OntologyTerm]:
        """Get term from cache if not expired."""
        cache_path = self._get_cache_path(term_id)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)

            # Check if cache is expired
            cached_at = datetime.fromisoformat(data["cached_at"])
            if datetime.now() - cached_at > self.ttl:
                return None

            # Convert source back to enum
            data["source"] = OntologySource(data["source"])
            if data.get("fetched_at"):
                data["fetched_at"] = datetime.fromisoformat(data["fetched_at"])

            return OntologyTerm(**data)
        except Exception as e:
            print(f"Error reading cache for {term_id}: {e}")
            return None

    def set(self, term_id: str, term: OntologyTerm):
        """Save term to cache."""
        cache_path = self._get_cache_path(term_id)

        try:
            data = term.model_dump()
            data["cached_at"] = datetime.now().isoformat()
            data["source"] = term.source.value
            if term.fetched_at:
                data["fetched_at"] = term.fetched_at.isoformat()

            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error writing cache for {term_id}: {e}")


class HybridOntologyService:
    """Hybrid ontology service that:
    1. Checks local cache first
    2. Falls back to APIs if enabled
    3. Falls back to hardcoded mappings
    4. Caches API responses.
    """

    def __init__(self):
        # Configuration
        self.use_apis = os.getenv("USE_ONTOLOGY_APIS", "true").lower() == "true"
        self.api_timeout = int(os.getenv("ONTOLOGY_API_TIMEOUT", "5"))
        self.cache_ttl_hours = int(os.getenv("ONTOLOGY_CACHE_TTL_HOURS", "24"))

        # Initialize components
        self.local_provider = LocalMappingsProvider()
        self.file_cache = FileCache(ttl_hours=self.cache_ttl_hours)

        # Initialize API clients if enabled
        if self.use_apis:
            self.hpo_client = HPOAPIClient(timeout=self.api_timeout)
            self.ols_client = OLSAPIClient(timeout=self.api_timeout)
            self.monarch_client = MonarchAPIClient(timeout=self.api_timeout)
        else:
            print("Ontology APIs disabled - using local mappings only")

        # In-memory cache for performance
        self._memory_cache = {}

    @lru_cache(maxsize=1000)
    def get_term(self, term_id: str) -> OntologyTerm:
        """Get ontology term with fallback strategy:
        1. Memory cache
        2. File cache
        3. APIs (if enabled)
        4. Local hardcoded mappings
        5. Unknown term placeholder.
        """
        # 1. Check memory cache
        if term_id in self._memory_cache:
            return self._memory_cache[term_id]

        # 2. Check file cache
        cached_term = self.file_cache.get(term_id)
        if cached_term:
            self._memory_cache[term_id] = cached_term
            return cached_term

        # 3. Try APIs if enabled
        if self.use_apis:
            api_term = self._fetch_from_apis(term_id)
            if api_term:
                self.file_cache.set(term_id, api_term)
                self._memory_cache[term_id] = api_term
                return api_term

        # 4. Try local hardcoded mappings
        local_term = self.local_provider.get_term(term_id)
        if local_term:
            self._memory_cache[term_id] = local_term
            return local_term

        # 5. Return unknown term placeholder
        unknown_term = OntologyTerm(
            id=term_id,
            label=f"Unknown term: {term_id}",
            source=OntologySource.LOCAL_HARDCODED,
            description="Term not found in any source",
        )
        self._memory_cache[term_id] = unknown_term
        return unknown_term

    def _fetch_from_apis(self, term_id: str) -> Optional[OntologyTerm]:
        """Try to fetch term from various APIs."""
        # Try APIs in order of preference
        if term_id.startswith("HP:"):
            # Try HPO API first (most specific for HPO terms)
            term = self.hpo_client.get_term(term_id)
            if term:
                return term

        # Try OLS (supports multiple ontologies)
        term = self.ols_client.get_term(term_id)
        if term:
            return term

        # Try Monarch (broader coverage)
        term = self.monarch_client.get_term(term_id)
        if term:
            return term

        return None

    def validate_term(self, term_id: str) -> bool:
        """Check if a term exists and is valid."""
        term = self.get_term(term_id)
        return not (term.label.startswith("Unknown term:") or term.is_obsolete)

    def get_term_label(self, term_id: str) -> str:
        """Get just the label for a term."""
        return self.get_term(term_id).label

    def validate_phenopacket(self, phenopacket: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all ontology terms in a phenopacket."""
        validation_results = {"valid_terms": [], "invalid_terms": [], "warnings": []}

        # Check phenotypic features
        for feature in phenopacket.get("phenotypicFeatures", []):
            if "type" in feature and "id" in feature["type"]:
                term_id = feature["type"]["id"]
                if self.validate_term(term_id):
                    validation_results["valid_terms"].append(term_id)
                else:
                    validation_results["invalid_terms"].append(term_id)

        # Check diseases
        for disease in phenopacket.get("diseases", []):
            if "term" in disease and "id" in disease["term"]:
                term_id = disease["term"]["id"]
                if self.validate_term(term_id):
                    validation_results["valid_terms"].append(term_id)
                else:
                    validation_results["invalid_terms"].append(term_id)

        # Overall validation status
        validation_results["is_valid"] = len(validation_results["invalid_terms"]) == 0

        return validation_results

    def enhance_phenopacket(self, phenopacket: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance phenopacket with official term labels."""
        # Enhance phenotypic features
        for feature in phenopacket.get("phenotypicFeatures", []):
            if "type" in feature and "id" in feature["type"]:
                term = self.get_term(feature["type"]["id"])
                feature["type"]["label"] = term.label

        # Enhance diseases
        for disease in phenopacket.get("diseases", []):
            if "term" in disease and "id" in disease["term"]:
                term = self.get_term(disease["term"]["id"])
                disease["term"]["label"] = term.label

        return phenopacket

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the service."""
        return {
            "apis_enabled": self.use_apis,
            "memory_cache_size": len(self._memory_cache),
            "file_cache_size": len(list(self.file_cache.cache_dir.glob("*.json"))),
            "local_mappings_count": len(self.local_provider.mappings),
        }


# Singleton instance
ontology_service = HybridOntologyService()
