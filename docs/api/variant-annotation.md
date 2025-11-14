# Variant Annotation API Reference

## Overview

The Variant Annotation API provides comprehensive genetic variant validation, annotation, and recoding services using the [Ensembl Variant Effect Predictor (VEP)](https://www.ensembl.org/info/docs/tools/vep/index.html). This API supports multiple variant notations and provides rich annotations including consequence predictions, population frequencies, and clinical significance.

**Base URL:** `/api/v2/variants/`

**Supported Variant Notations:**
- **HGVS** (Human Genome Variation Society): `NM_000458.4:c.544+1G>A`, `ENST00000366667.8:c.544+1G>A`
- **VCF** (Variant Call Format): `17-36459258-A-G`, `chr17-36459258-A-G`
- **rsID** (dbSNP reference SNP ID): `rs56116432`

**Key Features:**
- Automatic format detection and conversion
- VEP annotation with consequence prediction
- Variant recoding between formats (HGVS ↔ VCF ↔ rsID)
- Population frequency data (gnomAD)
- Clinical significance scores (CADD)
- Rate limiting with automatic retry
- Response caching for performance

---

## Authentication

All endpoints require JWT authentication via Bearer token.

**Request Header:**
```http
Authorization: Bearer <your-jwt-token>
```

**Obtaining a Token:**
```bash
# Login to get JWT token
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Token Usage:**
```bash
# Use token in subsequent requests
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'
```

---

## Endpoints

### 1. Validate Variant

Validates a variant notation and suggests corrections if invalid.

**Endpoint:** `POST /api/v2/variants/validate`

**Request Body:**
```json
{
  "variant": "NM_000458.4:c.544+1G>A"
}
```

**Parameters:**
- `variant` (string, required): Variant notation in HGVS, VCF, or rsID format

**Success Response (200 OK):**
```json
{
  "valid": true,
  "variant": "NM_000458.4:c.544+1G>A",
  "format": "hgvs",
  "message": "Valid variant notation"
}
```

**Error Response (400 Bad Request):**
```json
{
  "valid": false,
  "variant": "NM_000458.4:c544+1G>A",
  "format": "unknown",
  "message": "Invalid HGVS notation",
  "suggestions": [
    "Missing ':' after transcript ID",
    "Did you mean: NM_000458.4:c.544+1G>A?"
  ]
}
```

**Format Detection:**

| Input Format | Detected As | Example |
|--------------|-------------|---------|
| HGVS (transcript) | `hgvs` | `NM_000458.4:c.544+1G>A` |
| HGVS (genomic) | `hgvs` | `NC_000017.11:g.36459258A>G` |
| VCF | `vcf` | `17-36459258-A-G` |
| VCF (chr prefix) | `vcf` | `chr17-36459258-A-G` |
| rsID | `rsid` | `rs56116432` |

**Example Requests:**

```bash
# Valid HGVS notation
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# Valid VCF notation
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17-36459258-A-G"}'

# Valid rsID
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "rs56116432"}'

# Invalid notation (missing colon)
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4c.544+1G>A"}'
```

**Validation Rules:**

**HGVS Format:**
- Must include transcript ID: `NM_*`, `ENST*`, `NC_*`
- Must have `:` separator between transcript and variant
- Coding variants use `c.` prefix: `c.544+1G>A`
- Genomic variants use `g.` prefix: `g.36459258A>G`
- Protein variants use `p.` prefix: `p.Arg182Trp`

**VCF Format:**
- Must have 4 parts: `chrom-position-ref-alt`
- Chromosome can have `chr` prefix: `chr17` or `17`
- Position must be integer: `36459258`
- Ref and Alt must be DNA bases: `A`, `G`, `C`, `T`

**rsID Format:**
- Must start with `rs` prefix
- Followed by numeric ID: `rs56116432`

---

### 2. Annotate Variant

Retrieves comprehensive annotations from Ensembl VEP.

**Endpoint:** `POST /api/v2/variants/annotate`

**Request Body:**
```json
{
  "variant": "NM_000458.4:c.544+1G>A",
  "include_predictions": true
}
```

**Parameters:**
- `variant` (string, required): Variant notation in HGVS, VCF, or rsID format
- `include_predictions` (boolean, optional): Include in-silico predictions (default: true)

**Success Response (200 OK):**
```json
{
  "input": "NM_000458.4:c.544+1G>A",
  "annotation": {
    "assembly_name": "GRCh38",
    "seq_region_name": "17",
    "start": 36459258,
    "end": 36459258,
    "allele_string": "A/G",
    "strand": 1,
    "id": "rs56116432",
    "most_severe_consequence": "splice_donor_variant",
    "transcript_consequences": [
      {
        "gene_id": "ENSG00000108753",
        "gene_symbol": "HNF1B",
        "transcript_id": "ENST00000366667",
        "consequence_terms": ["splice_donor_variant"],
        "impact": "HIGH",
        "mane_select": "ENST00000366667.8",
        "hgvsc": "ENST00000366667.8:c.544+1G>A",
        "hgvsp": null,
        "cadd_phred": 34.0
      }
    ],
    "colocated_variants": [
      {
        "id": "rs56116432",
        "gnomad_af": 0.0001,
        "clin_sig": ["pathogenic"]
      }
    ]
  }
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Variant not found in VEP database"
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "Invalid variant format"
}
```

**Annotation Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `assembly_name` | string | Reference genome assembly (GRCh37/GRCh38) |
| `seq_region_name` | string | Chromosome number |
| `start` | integer | Variant start position (1-based) |
| `end` | integer | Variant end position (1-based) |
| `allele_string` | string | Reference/alternate alleles |
| `strand` | integer | DNA strand (1=forward, -1=reverse) |
| `id` | string | dbSNP rsID (if available) |
| `most_severe_consequence` | string | Most severe predicted consequence |
| `transcript_consequences` | array | Per-transcript annotations |
| `colocated_variants` | array | Known variants at same position |

**Transcript Consequence Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `gene_id` | string | Ensembl gene ID (ENSG*) |
| `gene_symbol` | string | HGNC gene symbol (e.g., HNF1B) |
| `transcript_id` | string | Ensembl transcript ID (ENST*) |
| `consequence_terms` | array | Sequence ontology terms |
| `impact` | string | Impact severity (HIGH/MODERATE/LOW/MODIFIER) |
| `mane_select` | string | MANE Select transcript (if applicable) |
| `hgvsc` | string | HGVS coding notation |
| `hgvsp` | string | HGVS protein notation (if applicable) |
| `cadd_phred` | float | CADD deleteriousness score |

**Consequence Terms (Sequence Ontology):**

| Term | Impact | Description |
|------|--------|-------------|
| `splice_donor_variant` | HIGH | Variant in splice donor site (GT) |
| `splice_acceptor_variant` | HIGH | Variant in splice acceptor site (AG) |
| `stop_gained` | HIGH | Introduces premature stop codon |
| `frameshift_variant` | HIGH | Insertion/deletion causing frameshift |
| `missense_variant` | MODERATE | Changes amino acid |
| `synonymous_variant` | LOW | No amino acid change |
| `intron_variant` | MODIFIER | Variant in intron |
| `5_prime_UTR_variant` | MODIFIER | Variant in 5' UTR |
| `3_prime_UTR_variant` | MODIFIER | Variant in 3' UTR |

**Example Requests:**

```bash
# Annotate HGVS variant
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# Annotate VCF variant
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17-36459258-A-G"}'

# Annotate rsID
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "rs56116432"}'
```

---

### 3. Recode Variant

Converts variant between different notation formats.

**Endpoint:** `POST /api/v2/variants/recode`

**Request Body:**
```json
{
  "variant": "rs56116432",
  "target_format": "hgvs"
}
```

**Parameters:**
- `variant` (string, required): Input variant notation
- `target_format` (string, optional): Desired output format (`hgvs`, `vcf`, `rsid`, `all`)
  - Default: `all` (returns all available formats)

**Success Response (200 OK):**
```json
{
  "input": "rs56116432",
  "recoding": {
    "id": ["rs56116432"],
    "hgvsg": ["NC_000017.11:g.36459258A>G"],
    "hgvsc": [
      "ENST00000366667.8:c.544+1G>A",
      "NM_000458.4:c.544+1G>A"
    ],
    "hgvsp": [],
    "spdi": {
      "seq_id": "NC_000017.11",
      "position": 36459257,
      "deleted_sequence": "A",
      "inserted_sequence": "G"
    },
    "vcf_string": "17:36459258-36459258:A:G"
  }
}
```

**Error Response (404 Not Found):**
```json
{
  "detail": "Unable to recode variant"
}
```

**Recoding Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | array | dbSNP rsIDs |
| `hgvsg` | array | HGVS genomic notations |
| `hgvsc` | array | HGVS coding notations (multiple transcripts) |
| `hgvsp` | array | HGVS protein notations |
| `spdi` | object | SPDI notation (NCBI Variation Services) |
| `vcf_string` | string | VCF-style notation |

**SPDI Format:**

SPDI (Sequence Position Deletion Insertion) is an unambiguous variant representation:

```json
{
  "seq_id": "NC_000017.11",        // RefSeq sequence ID
  "position": 36459257,             // 0-based position
  "deleted_sequence": "A",          // Reference allele
  "inserted_sequence": "G"          // Alternate allele
}
```

**Example Requests:**

```bash
# Recode rsID to all formats
curl -X POST http://localhost:8000/api/v2/variants/recode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "rs56116432"}'

# Recode HGVS to VCF format
curl -X POST http://localhost:8000/api/v2/variants/recode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A", "target_format": "vcf"}'

# Recode VCF to HGVS format
curl -X POST http://localhost:8000/api/v2/variants/recode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "17-36459258-A-G", "target_format": "hgvs"}'
```

**Conversion Examples:**

| Input Format | Input Example | Output Formats |
|--------------|---------------|----------------|
| rsID | `rs56116432` | HGVS, VCF, SPDI |
| HGVS | `NM_000458.4:c.544+1G>A` | rsID, VCF, SPDI |
| VCF | `17-36459258-A-G` | rsID, HGVS, SPDI |

---

### 4. Get Notation Suggestions

Provides helpful suggestions for fixing invalid variant notations.

**Endpoint:** `GET /api/v2/variants/suggest/{notation}`

**Parameters:**
- `notation` (string, required, path parameter): Invalid or partial variant notation

**Success Response (200 OK):**
```json
{
  "notation": "NM_000458.4c.544+1G>A",
  "suggestions": [
    "Missing ':' separator between transcript ID and variant position",
    "Did you mean: NM_000458.4:c.544+1G>A?",
    "HGVS format requires colon after transcript ID",
    "Example: NM_000458.4:c.544+1G>A"
  ]
}
```

**Common Issues Detected:**

| Issue | Input Example | Suggestion |
|-------|---------------|------------|
| Missing colon | `NM_000458.4c.544G>A` | Add `:` after transcript ID |
| Missing dot in protein | `p.Arg182Trp` needs `p.` | Use `p.Arg182Trp` format |
| Wrong separator | `17:36459258:A:G` | Use `-` for VCF: `17-36459258-A-G` |
| Missing chr prefix | `17-36459258-A-G` | Optionally add `chr`: `chr17-36459258-A-G` |
| Invalid bases | `17-36459258-X-Y` | Use valid DNA bases (A, C, G, T) |

**Example Requests:**

```bash
# Get suggestions for missing colon
curl -X GET http://localhost:8000/api/v2/variants/suggest/NM_000458.4c.544+1G>A \
  -H "Authorization: Bearer $TOKEN"

# Get suggestions for wrong separator
curl -X GET http://localhost:8000/api/v2/variants/suggest/17:36459258:A:G \
  -H "Authorization: Bearer $TOKEN"

# Get suggestions for incomplete notation
curl -X GET http://localhost:8000/api/v2/variants/suggest/NM_000458.4 \
  -H "Authorization: Bearer $TOKEN"
```

---

## Rate Limiting

The API implements rate limiting to comply with Ensembl VEP usage policies.

**Limits:**
- **Requests per second:** 15
- **Burst capacity:** 15 tokens
- **Refill rate:** 15 tokens/second

**Rate Limit Headers:**

Response includes rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
```

**Rate Limit Exceeded (429 Too Many Requests):**

```json
{
  "detail": "Rate limit exceeded. Retry after 2 seconds."
}
```

**Automatic Retry:**

The API automatically retries rate-limited requests with exponential backoff:

1. First retry: Wait 1 second
2. Second retry: Wait 2 seconds
3. Third retry: Wait 4 seconds
4. Maximum retries: 3

**Best Practices:**

- Use batch operations where possible
- Implement client-side rate limiting
- Cache responses for repeated queries
- Monitor `X-RateLimit-Remaining` header

---

## Caching

The API implements LRU (Least Recently Used) caching for performance.

**Cache Configuration:**
- **Cache size:** 1000 variants
- **Eviction policy:** LRU (least recently used)
- **Cache hit detection:** Automatic

**Cache Behavior:**

1. **First request:** Fetches from VEP API, stores in cache
2. **Subsequent requests:** Returns cached data (no VEP call)
3. **Cache full:** Evicts least recently used variant

**Cache Headers:**

```http
X-Cache-Hit: true
X-Cache-Size: 234
```

**Benefits:**

- Reduced VEP API load
- Faster response times (< 10ms vs ~500ms)
- No rate limit consumption for cached queries

**Limitations:**

- Cache persists only during server session
- Cache cleared on server restart
- No cache invalidation for stale data

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid variant format |
| 401 | Unauthorized | Missing or invalid JWT token |
| 404 | Not Found | Variant not found in VEP database |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (retry recommended) |
| 503 | Service Unavailable | VEP service temporarily unavailable |

### Error Response Format

All errors follow consistent JSON structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "VARIANT_NOT_FOUND",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Common Errors

**Invalid Variant Format (400):**
```json
{
  "detail": "Invalid variant format: NM_000458.4c.544G>A",
  "error_code": "INVALID_FORMAT",
  "suggestions": ["Missing ':' after transcript ID"]
}
```

**Authentication Failed (401):**
```json
{
  "detail": "Invalid authentication credentials",
  "error_code": "AUTH_FAILED"
}
```

**Variant Not Found (404):**
```json
{
  "detail": "Variant not found in Ensembl VEP database",
  "error_code": "VARIANT_NOT_FOUND"
}
```

**Rate Limit Exceeded (429):**
```json
{
  "detail": "Rate limit exceeded. Please retry after 2 seconds.",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 2
}
```

**VEP Service Unavailable (503):**
```json
{
  "detail": "Ensembl VEP service temporarily unavailable",
  "error_code": "VEP_UNAVAILABLE",
  "retry_after": 60
}
```

---

## Complete Examples

### Example 1: Validate and Annotate Workflow

```bash
# Step 1: Validate variant
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# Response: {"valid": true, "format": "hgvs"}

# Step 2: Annotate variant
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# Response: Full VEP annotation (see above)
```

### Example 2: Convert rsID to HGVS

```bash
# Step 1: Recode rsID to all formats
curl -X POST http://localhost:8000/api/v2/variants/recode \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "rs56116432"}'

# Response includes:
# - hgvsc: ["NM_000458.4:c.544+1G>A", ...]
# - hgvsg: ["NC_000017.11:g.36459258A>G"]
# - vcf_string: "17:36459258-36459258:A:G"

# Step 2: Use HGVS notation for annotation
curl -X POST http://localhost:8000/api/v2/variants/annotate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'
```

### Example 3: Fix Invalid Notation

```bash
# Step 1: Try to validate invalid notation
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4c.544+1G>A"}'

# Response: {"valid": false, "suggestions": ["Missing ':' ..."]}

# Step 2: Get detailed suggestions
curl -X GET http://localhost:8000/api/v2/variants/suggest/NM_000458.4c.544+1G>A \
  -H "Authorization: Bearer $TOKEN"

# Response: {"suggestions": ["Add ':' after transcript ID", ...]}

# Step 3: Validate corrected notation
curl -X POST http://localhost:8000/api/v2/variants/validate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant": "NM_000458.4:c.544+1G>A"}'

# Response: {"valid": true}
```

---

## Python Client Example

```python
import requests
from typing import Optional

class VariantAnnotationClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def validate(self, variant: str) -> dict:
        """Validate variant notation."""
        response = requests.post(
            f"{self.base_url}/variants/validate",
            headers=self.headers,
            json={"variant": variant}
        )
        response.raise_for_status()
        return response.json()

    def annotate(self, variant: str) -> dict:
        """Get VEP annotation for variant."""
        response = requests.post(
            f"{self.base_url}/variants/annotate",
            headers=self.headers,
            json={"variant": variant}
        )
        response.raise_for_status()
        return response.json()

    def recode(self, variant: str, target_format: Optional[str] = None) -> dict:
        """Convert variant between formats."""
        data = {"variant": variant}
        if target_format:
            data["target_format"] = target_format

        response = requests.post(
            f"{self.base_url}/variants/recode",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

# Usage
client = VariantAnnotationClient(
    base_url="http://localhost:8000/api/v2",
    token="your-jwt-token"
)

# Validate
result = client.validate("NM_000458.4:c.544+1G>A")
print(f"Valid: {result['valid']}")

# Annotate
annotation = client.annotate("rs56116432")
print(f"Consequence: {annotation['annotation']['most_severe_consequence']}")

# Recode
recoding = client.recode("rs56116432", target_format="hgvs")
print(f"HGVS notations: {recoding['recoding']['hgvsc']}")
```

---

## JavaScript/TypeScript Client Example

```typescript
interface ValidateResponse {
  valid: boolean;
  variant: string;
  format: string;
  message: string;
  suggestions?: string[];
}

interface AnnotateResponse {
  input: string;
  annotation: {
    most_severe_consequence: string;
    transcript_consequences: Array<{
      gene_symbol: string;
      consequence_terms: string[];
      impact: string;
    }>;
  };
}

class VariantAnnotationClient {
  private baseUrl: string;
  private token: string;

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    method: string,
    body?: any
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return response.json();
  }

  async validate(variant: string): Promise<ValidateResponse> {
    return this.request<ValidateResponse>(
      '/variants/validate',
      'POST',
      { variant }
    );
  }

  async annotate(variant: string): Promise<AnnotateResponse> {
    return this.request<AnnotateResponse>(
      '/variants/annotate',
      'POST',
      { variant }
    );
  }

  async recode(variant: string, targetFormat?: string): Promise<any> {
    return this.request(
      '/variants/recode',
      'POST',
      { variant, target_format: targetFormat }
    );
  }
}

// Usage
const client = new VariantAnnotationClient(
  'http://localhost:8000/api/v2',
  'your-jwt-token'
);

// Validate
const validation = await client.validate('NM_000458.4:c.544+1G>A');
console.log(`Valid: ${validation.valid}`);

// Annotate
const annotation = await client.annotate('rs56116432');
console.log(`Consequence: ${annotation.annotation.most_severe_consequence}`);
```

---

## Testing

### Running Tests

```bash
# Run all variant annotation tests
cd backend
uv run pytest tests/test_variant_validator_enhanced.py -v

# Run with coverage
uv run pytest tests/test_variant_validator_enhanced.py --cov=app/phenopackets/validation

# Run integration tests
uv run pytest tests/test_variant_validator_api_integration.py -v
```

### Test Coverage

- **Unit tests:** 83 tests covering 99% of code
- **Integration tests:** 18 tests for API endpoints
- **Total execution time:** ~7 seconds

---

## Performance Considerations

### Response Times

| Operation | First Call | Cached Call |
|-----------|-----------|-------------|
| Validate | ~10ms | ~5ms |
| Annotate (VEP API) | ~500ms | ~10ms |
| Recode (VEP API) | ~600ms | ~10ms |

### Optimization Tips

1. **Use caching:** Repeated queries return instantly
2. **Batch operations:** Group related queries together
3. **Validate first:** Check format before annotation
4. **Monitor rate limits:** Watch `X-RateLimit-Remaining` header

---

## References

- [Ensembl VEP Documentation](https://www.ensembl.org/info/docs/tools/vep/index.html)
- [HGVS Nomenclature](https://varnomen.hgvs.org/)
- [VCF Format Specification](https://samtools.github.io/hts-specs/VCFv4.3.pdf)
- [dbSNP Database](https://www.ncbi.nlm.nih.gov/snp/)
- [Sequence Ontology](http://www.sequenceontology.org/)
- [CADD Score](https://cadd.gs.washington.edu/)
- [gnomAD Database](https://gnomad.broadinstitute.org/)

---

## Support

For issues or questions:
- **GitHub Issues:** [hnf1b-db/issues](https://github.com/yourusername/hnf1b-db/issues)
- **Documentation:** [docs/variant-annotation-implementation-plan.md](/docs/variant-annotation-implementation-plan.md)
- **API Version:** v2 (current)
- **Last Updated:** 2025-01-15
