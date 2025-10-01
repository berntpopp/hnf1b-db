#!/usr/bin/env python3
"""Example of using the hybrid ontology service with phenopackets."""

from datetime import datetime
from typing import Any, Dict

from app.services.ontology_service import ontology_service


def create_phenopacket_with_validation(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a phenopacket with ontology validation and enhancement.

    This demonstrates how the hybrid service works without downloading
    large ontology files.
    """
    # Create basic phenopacket structure
    phenopacket = {
        "id": f"phenopacket:{patient_data['id']}",
        "subject": {
            "id": patient_data["id"],
            "sex": patient_data.get("sex", "UNKNOWN_SEX"),
        },
        "phenotypicFeatures": [],
        "diseases": [],
        "metaData": {
            "created": datetime.now().isoformat(),
            "phenopacketSchemaVersion": "2.0.0",
        },
    }

    # Add phenotypic features with validation
    for feature_id in patient_data.get("features", []):
        # Validate the term exists
        if ontology_service.validate_term(feature_id):
            term = ontology_service.get_term(feature_id)
            phenopacket["phenotypicFeatures"].append(
                {
                    "type": {
                        "id": feature_id,
                        "label": term.label,  # Get official label
                    }
                }
            )
            print(
                f"✓ Added feature: {feature_id} - {term.label} (source: {term.source.value})"
            )
        else:
            print(f"⚠ Skipped invalid term: {feature_id}")

    # Add diseases with validation
    for disease_id in patient_data.get("diseases", []):
        if ontology_service.validate_term(disease_id):
            term = ontology_service.get_term(disease_id)
            phenopacket["diseases"].append(
                {"term": {"id": disease_id, "label": term.label}}
            )
            print(
                f"✓ Added disease: {disease_id} - {term.label} (source: {term.source.value})"
            )
        else:
            print(f"⚠ Skipped invalid term: {disease_id}")

    return phenopacket


def main():
    """Demonstrate the hybrid ontology service with phenopackets."""
    print("Phenopackets with Hybrid Ontology Service")
    print("=" * 50)

    # Example patient data
    patient = {
        "id": "IND001",
        "sex": "FEMALE",
        "features": [
            "HP:0012622",  # Chronic kidney disease (in local mappings)
            "HP:0100611",  # Multiple glomerular cysts (in local mappings)
            "HP:0002917",  # Hypomagnesemia (might use API)
            "HP:0000819",  # Diabetes mellitus (might use API)
            "HP:9999999",  # Invalid term for testing
        ],
        "diseases": [
            "MONDO:0018874",  # HNF1B-related disease (might use API)
            "MONDO:0005147",  # Type 2 diabetes mellitus (might use API)
            "MONDO:INVALID",  # Invalid for testing
        ],
    }

    print(f"\nProcessing patient: {patient['id']}")
    print("-" * 40)

    # Create phenopacket with validation
    phenopacket = create_phenopacket_with_validation(patient)

    # Show results
    print("\n" + "=" * 50)
    print("Created Phenopacket:")
    print(f"  ID: {phenopacket['id']}")
    print(f"  Features: {len(phenopacket['phenotypicFeatures'])} valid terms")
    print(f"  Diseases: {len(phenopacket['diseases'])} valid terms")

    # Validate the complete phenopacket
    print("\nValidating complete phenopacket...")
    validation = ontology_service.validate_phenopacket(phenopacket)
    print(f"  Valid terms: {len(validation['valid_terms'])}")
    print(f"  Invalid terms: {len(validation['invalid_terms'])}")
    print(f"  Overall valid: {validation['is_valid']}")

    # Show service statistics
    print("\nOntology Service Statistics:")
    stats = ontology_service.get_statistics()
    print(f"  APIs enabled: {stats['apis_enabled']}")
    print(f"  Terms in memory cache: {stats['memory_cache_size']}")
    print(f"  Terms in file cache: {stats['file_cache_size']}")
    print(f"  Local mappings available: {stats['local_mappings_count']}")

    print("\n" + "=" * 50)
    print("Key Benefits of Hybrid Approach:")
    print("• No large ontology files to download (saves ~150MB)")
    print("• Works offline with local mappings")
    print("• Can fetch additional terms from APIs when online")
    print("• Caches API responses for performance")
    print("• Validates terms automatically")
    print("• Provides official term labels")


if __name__ == "__main__":
    main()
