# API Reference Documentation

This directory contains detailed API reference documentation for the HNF1B Database backend services.

## Available Documentation

### Variant Annotation API
**File:** [variant-annotation.md](variant-annotation.md)

Comprehensive reference for the VEP-powered variant annotation system.

**Endpoints:**
- `POST /api/v2/variants/validate` - Validate variant notations
- `POST /api/v2/variants/annotate` - Get VEP annotations
- `POST /api/v2/variants/recode` - Convert between formats
- `GET /api/v2/variants/suggest/{notation}` - Get notation suggestions

**Features:**
- HGVS, VCF, and rsID format support
- Ensembl VEP integration
- Rate limiting (15 req/sec)
- LRU caching (1000 variants)
- Consequence predictions (CADD, gnomAD)

**Documentation Includes:**
- Authentication guide
- Endpoint specifications
- Request/response examples
- Error handling
- Python and JavaScript client examples
- Performance considerations

---

### Variant Search API
**File:** [VARIANT_SEARCH.md](VARIANT_SEARCH.md)

Documentation for the phenopacket variant search functionality.

**Endpoint:**
- `POST /api/v2/phenopackets/search` - Search phenopackets by variant criteria

**Features:**
- 8 search fields (HGVS, coordinates, type, classification, etc.)
- JSONB GIN index optimization (10x faster)
- Batch operations

---

## Interactive API Documentation

When the backend server is running, you can access interactive API documentation:

### Swagger UI (Recommended)
```
http://localhost:8000/docs
```
- Try out API endpoints directly from the browser
- See request/response schemas
- Test authentication with JWT tokens
- View comprehensive OpenAPI documentation

### ReDoc (Alternative)
```
http://localhost:8000/redoc
```
- Clean, organized API reference
- Better for reading and understanding API structure
- Export OpenAPI spec for tooling

---

## Quick Start

### 1. Start the Backend Server
```bash
# From project root
make hybrid-up    # Start PostgreSQL + Redis
make backend      # Start backend server

# Or from backend directory
cd backend
uv run uvicorn app.main:app --reload
```

### 2. Get Authentication Token
```bash
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Save the token
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. Test Variant Annotation
```bash
# Validate a variant
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notation": "NM_000458.4:c.544+1G>A"}'

# Annotate with VEP
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'
```

---

## Related Documentation

- **User Guide:** [../user-guide/variant-annotation.md](../user-guide/variant-annotation.md) - Practical workflows and examples
- **Developer Guide:** [../variant-annotation-implementation-plan.md](../variant-annotation-implementation-plan.md) - Implementation details
- **Backend README:** [../../backend/README.md](../../backend/README.md) - Backend setup and architecture

---

## API Design Principles

### RESTful Design
- Resource-oriented URLs
- Standard HTTP methods (GET, POST, PUT, DELETE)
- JSON request/response bodies
- Proper HTTP status codes

### Authentication
- JWT bearer tokens for all endpoints
- Token expiration: 24 hours
- Refresh tokens available

### Error Handling
- Consistent error response format
- Descriptive error messages
- Appropriate HTTP status codes
- Suggestions for invalid input

### Performance
- LRU caching for repeated queries
- Rate limiting to protect external APIs
- JSONB GIN indexes for fast search
- Async operations throughout

### Standards Compliance
- GA4GH Phenopackets v2
- GA4GH VRS 2.0
- HGVS nomenclature
- VCF specification
- OpenAPI 3.0

---

## Contributing

When adding new API endpoints, please:

1. **Write OpenAPI documentation** with comprehensive descriptions and examples
2. **Create API reference documentation** in this directory
3. **Add user guide examples** in `../user-guide/`
4. **Update this README** with links to new documentation
5. **Write tests** with >90% coverage
6. **Follow naming conventions** (RESTful URLs, consistent response formats)

---

## Support

- **GitHub Issues:** [hnf1b-db/issues](https://github.com/yourusername/hnf1b-db/issues)
- **Tag:** `api-documentation`

**Last Updated:** 2025-01-15
