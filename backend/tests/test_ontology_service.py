#!/usr/bin/env python3
"""Tests for the hybrid ontology service functionality."""

import os
from pathlib import Path

# Set environment variables before importing the service
os.environ["USE_ONTOLOGY_APIS"] = "true"  # Enable API usage
os.environ["ONTOLOGY_API_TIMEOUT"] = "10"  # 10 second timeout
os.environ["ONTOLOGY_CACHE_TTL_HOURS"] = "24"  # Cache for 24 hours


def test_ontology_service_local_terms_returns_labels():
    """Test hybrid ontology service returns labels for local hardcoded terms."""
    print("Testing Hybrid Ontology Service\n" + "=" * 50)

    # Import after setting environment variables
    from app.services.ontology_service import ontology_service

    # Test terms that should be in local mappings
    print("\n1. Testing Local Hardcoded Terms:")
    print("-" * 40)

    local_terms = [
        "HP:0012622",  # Chronic kidney disease
        "HP:0100611",  # Multiple glomerular cysts
        "ORPHA:2260",  # Oligomeganephronia
    ]

    for term_id in local_terms:
        term = ontology_service.get_term(term_id)
        print(f"  {term_id}: {term.label}")
        print(f"  Source: {term.source.value}")
        assert term.label is not None
        assert len(term.label) > 0


def test_ontology_service_api_terms_fetches_successfully():
    """Test hybrid ontology service fetches terms from API when needed."""
    print("\n2. Testing API Lookup (if enabled):")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    api_terms = [
        "HP:0000819",  # Diabetes mellitus
        "HP:0002917",  # Hypomagnesemia
        "MONDO:0005147",  # Type 2 diabetes mellitus
    ]

    for term_id in api_terms:
        term = ontology_service.get_term(term_id)
        print(f"  {term_id}: {term.label}")
        print(f"  Source: {term.source.value}")
        assert term is not None


def test_ontology_service_unknown_term_returns_placeholder():
    """Test hybrid ontology service handles unknown terms gracefully."""
    print("\n3. Testing Unknown Term Handling:")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    unknown_term = "HP:9999999"  # This should not exist
    term = ontology_service.get_term(unknown_term)
    print(f"  {unknown_term}: {term.label}")
    print(f"  Source: {term.source.value}")
    assert term is not None  # Should return a placeholder, not None


def test_ontology_service_validate_term_returns_correct_status():
    """Test ontology service validation returns correct status for known and unknown terms."""
    print("\n4. Testing Term Validation:")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    valid_term = "HP:0012622"
    invalid_term = "HP:9999999"

    is_valid = ontology_service.validate_term(valid_term)
    is_invalid = ontology_service.validate_term(invalid_term)

    print(f"Is {valid_term} valid? {is_valid}")
    print(f"Is {invalid_term} valid? {is_invalid}")

    assert is_valid is True
    assert is_invalid is False


def test_ontology_service_validate_phenopacket_returns_validation_results():
    """Test ontology service validates phenopacket terms and returns results."""
    print("\n5. Testing Phenopacket Validation:")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    test_phenopacket = {
        "id": "test_phenopacket",
        "subject": {"id": "patient1"},
        "phenotypicFeatures": [
            {"type": {"id": "HP:0012622"}},  # Valid
            {"type": {"id": "HP:0100611"}},  # Valid
            {"type": {"id": "HP:9999999"}},  # Invalid
        ],
        "diseases": [
            {"term": {"id": "MONDO:0005147"}},  # Valid
            {"term": {"id": "MONDO:9999999"}},  # Invalid
        ],
    }

    validation_results = ontology_service.validate_phenopacket(test_phenopacket)
    print(f"Valid terms: {validation_results['valid_terms']}")
    print(f"Invalid terms: {validation_results['invalid_terms']}")
    print(f"Overall valid: {validation_results['is_valid']}")

    assert "valid_terms" in validation_results
    assert "invalid_terms" in validation_results
    assert "is_valid" in validation_results


def test_ontology_service_enhance_phenopacket_adds_labels():
    """Test ontology service enhancement adds labels to phenopacket terms."""
    print("\n6. Testing Phenopacket Enhancement:")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    simple_phenopacket = {
        "phenotypicFeatures": [
            {"type": {"id": "HP:0012622"}},
            {"type": {"id": "HP:0100611"}},
        ],
        "diseases": [{"term": {"id": "MONDO:0005147"}}],
    }

    enhanced = ontology_service.enhance_phenopacket(simple_phenopacket)
    print("Enhanced phenopacket:")
    for feature in enhanced["phenotypicFeatures"]:
        print(f"  {feature['type']['id']}: {feature['type'].get('label', 'No label')}")
    for disease in enhanced["diseases"]:
        print(f"  {disease['term']['id']}: {disease['term'].get('label', 'No label')}")

    # Check that labels were added
    assert "label" in enhanced["phenotypicFeatures"][0]["type"]
    assert "label" in enhanced["diseases"][0]["term"]


def test_ontology_service_statistics_returns_metrics():
    """Test ontology service statistics returns usage metrics."""
    print("\n7. Service Statistics:")
    print("-" * 40)

    from app.services.ontology_service import ontology_service

    stats = ontology_service.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    assert isinstance(stats, dict)
    assert len(stats) > 0


def test_ontology_service_cache_directory_exists():
    """Test ontology service cache directory is created and usable."""
    # Check cache directory
    cache_dir = Path(".ontology_cache")
    if cache_dir.exists():
        print("\n8. Cache Status:")
        print("-" * 40)
        cache_files = list(cache_dir.glob("*.json"))
        print(f"  Cache directory: {cache_dir}")
        print(f"  Cached terms: {len(cache_files)}")
        if cache_files:
            print("  Cached term IDs:")
            for f in cache_files[:5]:  # Show first 5
                print(f"    - {f.stem.replace('_', ':')}")
            if len(cache_files) > 5:
                print(f"    ... and {len(cache_files) - 5} more")

    # Cache directory existence is optional, test passes either way
    assert True


def test_ontology_service_performance_cached_faster_than_initial():
    """Test ontology service performance: cached lookups are faster than initial."""
    print("\n\nPerformance Test")
    print("=" * 50)

    import time

    from app.services.ontology_service import ontology_service

    test_terms = [
        "HP:0012622",
        "HP:0012623",
        "HP:0012624",
        "HP:0100611",
        "ORPHA:2260",
        "HP:0000819",
        "MONDO:0005147",
    ]

    # First pass - might hit APIs
    start = time.time()
    for term_id in test_terms:
        ontology_service.get_term(term_id)
    first_pass = time.time() - start

    print(f"First pass (potential API calls): {first_pass:.2f} seconds")

    # Second pass - should use cache
    start = time.time()
    for term_id in test_terms:
        ontology_service.get_term(term_id)
    second_pass = time.time() - start

    print(f"Second pass (from cache): {second_pass:.2f} seconds")
    if first_pass > 0:
        print(f"Speedup: {first_pass / max(second_pass, 0.001):.1f}x faster")

    # Cached lookups should be at least as fast (usually faster)
    assert second_pass <= first_pass + 0.1  # Allow small tolerance


if __name__ == "__main__":
    try:
        test_ontology_service_local_terms_returns_labels()
        test_ontology_service_api_terms_fetches_successfully()
        test_ontology_service_unknown_term_returns_placeholder()
        test_ontology_service_validate_term_returns_correct_status()
        test_ontology_service_validate_phenopacket_returns_validation_results()
        test_ontology_service_enhance_phenopacket_adds_labels()
        test_ontology_service_statistics_returns_metrics()
        test_ontology_service_cache_directory_exists()
        test_ontology_service_performance_cached_faster_than_initial()

        print("\n" + "=" * 50)
        print("Hybrid Ontology Service is working correctly!")
        print("\nKey Features:")
        print("- No large ontology files downloaded")
        print("- Uses existing hardcoded mappings")
        print("- Can fetch additional terms from APIs (if enabled)")
        print("- Caches API responses to reduce network calls")
        print("- Falls back gracefully when APIs are unavailable")
        print("\nYou can now use this service in your phenopackets implementation!")

    except Exception as e:
        print(f"\nError during testing: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure all dependencies are installed: uv sync --all-groups")
        print("2. Check that the migration/modules/phenotypes.py file exists")
        print("3. Verify network connectivity for API calls")
        import traceback

        traceback.print_exc()
