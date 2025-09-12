# Hybrid Ontology Service for Phenopackets

## Overview

The HNF1B-API now includes a hybrid ontology service that provides ontology term validation and enrichment **without downloading large ontology files**. This service combines:

1. **Local hardcoded mappings** (existing approach)
2. **API lookups** (when online)
3. **Intelligent caching** (for performance)

## Key Benefits

✅ **No large files**: Saves ~150MB of ontology downloads (HPO, MONDO, etc.)  
✅ **Works offline**: Falls back to existing hardcoded mappings  
✅ **Always current**: APIs provide latest ontology versions  
✅ **Fast**: Caches responses to avoid repeated API calls  
✅ **Flexible**: Can be disabled for fully offline operation  

## Architecture

```
User Request
     ↓
Memory Cache → Found? → Return
     ↓ Not found
File Cache → Found? → Return  
     ↓ Not found
APIs (if enabled) → Found? → Cache & Return
     ↓ Not found
Local Mappings → Found? → Return
     ↓ Not found
Unknown Term Placeholder
```

## Configuration

Add to `.env`:

```bash
# Ontology Service Configuration
USE_ONTOLOGY_APIS=true          # Enable/disable API lookups
ONTOLOGY_API_TIMEOUT=5           # API timeout in seconds
ONTOLOGY_CACHE_TTL_HOURS=24      # Cache duration in hours
```

## Usage Examples

### Basic Term Lookup

```python
from app.services.ontology_service import ontology_service

# Get term information
term = ontology_service.get_term("HP:0012622")
print(f"{term.id}: {term.label}")
# Output: HP:0012622: Chronic kidney disease

# Validate term
is_valid = ontology_service.validate_term("HP:0012622")
# Output: True
```

### Phenopacket Validation

```python
# Validate all terms in a phenopacket
phenopacket = {
    "phenotypicFeatures": [
        {"type": {"id": "HP:0012622"}},
        {"type": {"id": "HP:9999999"}}  # Invalid
    ]
}

results = ontology_service.validate_phenopacket(phenopacket)
print(f"Valid: {results['valid_terms']}")
print(f"Invalid: {results['invalid_terms']}")
```

### Phenopacket Enhancement

```python
# Add official labels to all terms
phenopacket = ontology_service.enhance_phenopacket(phenopacket)
# Terms now have official labels from APIs or local mappings
```

## API Sources

The service queries multiple APIs with automatic fallback:

1. **HPO JAX API** - Primary source for HPO terms
   - URL: https://hpo.jax.org/api/hpo
   - Best for: Human Phenotype Ontology terms

2. **EBI OLS API** - Ontology Lookup Service
   - URL: https://www.ebi.ac.uk/ols4/api
   - Best for: Multiple ontologies (HPO, MONDO, ORDO)

3. **Monarch Initiative API** - Broad coverage
   - URL: https://api.monarchinitiative.org/v3
   - Best for: Cross-ontology relationships

## Local Mappings

The service includes hardcoded mappings for common HNF1B terms:

- **Kidney stages**: HP:0012622-HP:0012626 (CKD stages 1-5)
- **Kidney pathology**: HP:0100611 (Multiple glomerular cysts), ORPHA:2260 (Oligomeganephronia)
- **Common features**: Diabetes, hypomagnesemia, genital abnormalities
- **HNF1B disease**: MONDO:0018874

## Cache Management

### File Cache Location
- Directory: `.ontology_cache/`
- Format: JSON files per term
- TTL: Configurable (default 24 hours)

### Clear Cache
```bash
# Remove all cached terms
rm -rf .ontology_cache/
```

### Cache Statistics
```python
stats = ontology_service.get_statistics()
print(f"Cached terms: {stats['file_cache_size']}")
```

## Performance

- **First lookup**: ~500ms (API call)
- **Cached lookup**: <1ms (memory cache)
- **Speedup**: ~500-1000x for cached terms

## Offline Mode

For fully offline operation:

```bash
# In .env
USE_ONTOLOGY_APIS=false
```

The service will only use local hardcoded mappings (19 core terms for HNF1B).

## Testing

Run the test scripts:

```bash
# Test ontology service
uv run python test_ontology_service.py

# Example with phenopackets
uv run python examples/phenopackets_with_ontology.py
```

## Migration Integration

The ontology service integrates seamlessly with phenopackets migration:

```python
from app.services.ontology_service import ontology_service

def convert_to_phenopacket(data):
    phenopacket = {...}
    
    # Validate terms during conversion
    for feature in features:
        if ontology_service.validate_term(feature["id"]):
            term = ontology_service.get_term(feature["id"])
            # Use official label
            feature["label"] = term.label
    
    return phenopacket
```

## Troubleshooting

### APIs Not Working
- Check internet connection
- Verify `USE_ONTOLOGY_APIS=true` in `.env`
- Check API timeout setting

### Cache Issues
- Clear cache: `rm -rf .ontology_cache/`
- Check disk space for cache directory
- Verify write permissions

### Missing Terms
- Term might not exist in any source
- Add to local mappings in `app/services/ontology_service.py`
- Check if term ID is correctly formatted (e.g., "HP:0012622")

## Future Enhancements

Potential improvements:
- Redis cache for multi-instance deployments
- Batch API requests for bulk operations
- Additional ontology sources (BioPortal, UMLS)
- Ontology hierarchy traversal
- Term relationship queries

## Summary

The hybrid ontology service provides the best of both worlds:
- **No large downloads** required
- **Works offline** with local mappings
- **Enhanced online** with API lookups
- **Fast** with intelligent caching
- **Simple** to use and configure

This approach is perfect for the phenopackets refactoring, providing ontology support without the overhead of managing large ontology files.