# HNF1B Database SEO & Authority Optimization Plan

**Goal:** Transform HNF1B-db into the definitive, most authoritative online resource for HNF1B-related disease and mutations.

**Date:** 2025-12-13
**Status:** Draft for Review

---

## Executive Summary

After analyzing your current implementation, competitive landscape, and SEO best practices for medical/genetic databases, I've identified **45+ improvement opportunities** organized into 8 priority tiers. Your codebase already has excellent foundations (GA4GH compliance, structured data, good technical SEO), but there are significant opportunities to establish dominance in this niche.

### Current Competitive Landscape

| Resource | Authority | Content Depth | Specialty |
|----------|-----------|---------------|-----------|
| [OMIM](https://www.omim.org/entry/137920) | Very High | Comprehensive gene-disease | General genetics |
| [GeneCards](https://www.genecards.org/cgi-bin/carddisp.pl?gene=HNF1B) | Very High | Gene overview | General genetics |
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Very High | Variant classifications | Variant interpretation |
| [NIH GTR](https://www.ncbi.nlm.nih.gov/gtr/genes/6928/) | High | Testing info | Genetic testing |
| [Diabetes Genes (UK)](https://www.diabetesgenes.org/what-is-mody/hnf1b-mody-rcad/) | High | MODY focus | Clinical |
| [MedlinePlus](https://medlineplus.gov/genetics/gene/hnf1b/) | Medium | Patient education | Consumer health |
| [LOVD](https://www.lovd.nl/) | Medium | Locus-specific variants | Variant curation |
| **HNF1B-db (You)** | **Low-Medium** | **Excellent data, limited content** | **HNF1B-specific** |

### Your Key Advantage
You are the **ONLY database exclusively focused on HNF1B** with:
- 864 phenopackets (individual patient phenotypes)
- 198 curated variants with VEP annotations
- 141 publications with literature tracking
- GA4GH Phenopackets v2 compliance (cutting-edge standard)
- Genotype-phenotype correlations
- Survival analysis capabilities

This niche focus is your path to authority.

---

## Priority 1: Critical SEO Fixes (Impact: Very High, Effort: Low)

### 1.1 Dynamic Sitemap Generation

**Current:** Static sitemap with only 7 URLs
**Problem:** Google can't discover 864 phenopacket pages, 198 variant pages, 141 publication pages

**Solution:** Generate dynamic sitemap including all resources

```xml
<!-- sitemap-index.xml -->
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://hnf1b.org/sitemap-static.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://hnf1b.org/sitemap-phenopackets.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://hnf1b.org/sitemap-variants.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://hnf1b.org/sitemap-publications.xml</loc>
  </sitemap>
</sitemapindex>
```

**Implementation Options:**
- A) Backend endpoint that generates sitemaps from DB
- B) Build-time generation during deployment
- C) Vite plugin (vite-plugin-sitemap with dynamic routes)

### 1.2 FAQPage Structured Data

**Current:** FAQ content exists but no schema markup
**Impact:** Enables FAQ rich snippets in Google search results

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is HNF1B-related disease?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "HNF1B-related disease refers to a spectrum of conditions..."
      }
    }
  ]
}
```

**Add to:** `frontend/src/views/FAQ.vue` - inject dynamically from faqContent.json

### 1.3 BreadcrumbList Structured Data

**Current:** Visual breadcrumbs exist but no schema
**Impact:** Shows navigation path in search results

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://hnf1b.org/"},
    {"@type": "ListItem", "position": 2, "name": "Variants", "item": "https://hnf1b.org/variants"},
    {"@type": "ListItem", "position": 3, "name": "c.544+1G>A"}
  ]
}
```

### 1.4 Individual Page Meta Tags

**Current:** SPA with static meta tags
**Problem:** All pages share same title/description in search results

**Solution:** Use `vue-meta` or `@unhead/vue` for per-route meta management

```javascript
// PageVariant.vue
useHead({
  title: `${variant.hgvs_c} - HNF1B Variant | HNF1B Database`,
  meta: [
    { name: 'description', content: `Detailed information about HNF1B variant ${variant.hgvs_c}. CADD: ${variant.cadd}, gnomAD: ${variant.gnomad}, Classification: ${variant.acmg}` }
  ]
})
```

---

## Priority 2: E-E-A-T Authority Building (Impact: Very High, Effort: Medium)

Medical/health content falls under **YMYL (Your Money or Your Life)** - Google's highest scrutiny category. You MUST demonstrate:

### 2.1 Expert Credentials & Author Pages

**Add to About page:**
```html
<section id="medical-advisory">
  <h2>Medical Advisory Board</h2>
  <div class="expert-card">
    <img src="expert-photo.jpg" alt="Dr. Name">
    <h3>Dr. [Name], MD, PhD</h3>
    <p>Position at Institution</p>
    <p>Board Certification: [Specialty]</p>
    <p>ORCID: <a href="https://orcid.org/0000-...">0000-...</a></p>
    <p>Publications: [count] on HNF1B</p>
  </div>
</section>
```

**Schema markup:**
```json
{
  "@type": "Person",
  "name": "Dr. Name",
  "jobTitle": "Medical Advisor",
  "affiliation": {"@type": "Organization", "name": "Institution"},
  "sameAs": ["https://orcid.org/...", "https://pubmed.ncbi.nlm.nih.gov/?term=author..."]
}
```

### 2.2 Content Review Notices

**Add visible notices:**
```html
<div class="medical-review-badge">
  <v-icon>mdi-shield-check</v-icon>
  <span>Medically reviewed by Dr. [Name], MD</span>
  <span>Last updated: December 2025</span>
</div>
```

### 2.3 Institutional Affiliation Prominence

Your current schema references BIH/Charité. Make this MORE visible:

```html
<footer>
  <img src="charite-logo.svg" alt="Charité - Universitätsmedizin Berlin">
  <img src="bih-logo.svg" alt="Berlin Institute of Health">
  <p>Affiliated with Berlin Institute of Health at Charité</p>
  <p>Funded by [Grant/Funding Source]</p>
</footer>
```

### 2.4 Citation & Academic Credibility

**Create DOI for database:**
- Register with Zenodo or DataCite for a citable DOI
- Add CITATION.cff to repository
- Submit to re3data.org (Registry of Research Data Repositories)
- Register in FAIRsharing.org

**Display prominently:**
```html
<div class="citation-box">
  <p>DOI: <a href="https://doi.org/10.5281/zenodo.XXXXXXX">10.5281/zenodo.XXXXXXX</a></p>
  <p>Cited by: [count] publications</p>
</div>
```

---

## Priority 3: Content Gap Analysis & Creation (Impact: Very High, Effort: High)

### 3.1 Educational Content Pages (New Routes)

Create comprehensive educational pages targeting high-value search queries:

| Page | Target Keywords | Content |
|------|-----------------|---------|
| `/disease/overview` | "hnf1b disease", "hnf1b syndrome" | Comprehensive disease overview |
| `/disease/symptoms` | "hnf1b symptoms", "rcad symptoms" | Symptom guide with HPO mappings |
| `/disease/diagnosis` | "hnf1b diagnosis", "mody5 testing" | Diagnostic criteria, genetic testing |
| `/disease/treatment` | "hnf1b treatment", "mody5 management" | Management guidelines |
| `/disease/inheritance` | "hnf1b inheritance", "17q12 deletion" | Genetic counseling info |
| `/research/genotype-phenotype` | "hnf1b genotype phenotype correlation" | Your unique data analysis |
| `/resources/patient-guide` | "hnf1b patient information" | Plain-language patient resource |
| `/resources/clinician-guide` | "hnf1b clinical guidelines" | For healthcare providers |

### 3.2 Variant Detail Page Enhancement

**Current:** Basic variant information
**Enhanced content per variant:**

```markdown
## Variant: NM_000458.4:c.544+1G>A

### Clinical Summary
- Classification: Pathogenic
- Evidence: PS3, PM2, PP3 (per ACMG guidelines)
- First reported: [Publication, Year]

### Population Data
- gnomAD: Not observed (0/282,912 alleles)
- ClinVar: [Link to entry]
- LOVD: [Link to entry]

### Functional Impact
- Protein effect: Splice donor disruption
- Domain affected: POU-specific domain
- Mechanism: Loss of function

### Associated Phenotypes (from this database)
- Renal cysts: 85% (17/20 individuals)
- Diabetes: 60% (12/20 individuals)
- [Interactive phenotype chart]

### Literature
- [Expandable list of 5 publications mentioning this variant]

### Submit Data
[Form to submit new clinical observations for this variant]
```

### 3.3 Publication Detail Page Enhancement

**Add to each publication:**
- Abstract (fetch from PubMed via existing integration)
- Linked phenopackets from this database
- Linked variants mentioned
- "Add to bibliography" export (RIS, BibTeX)
- Altmetric badge

### 3.4 Blog/News Section (New Feature)

Regular content updates signal freshness to Google:

```
/news/
├── 2025-12-01-new-variant-submissions
├── 2025-11-15-survival-analysis-update
├── 2025-10-01-ga4gh-phenopackets-compliance
```

---

## Priority 4: Technical SEO Improvements (Impact: High, Effort: Medium)

### 4.1 Server-Side Rendering (SSR) or Prerendering

**Current:** Client-side SPA (poor for SEO crawlers)
**Problem:** Googlebot may not fully render JavaScript content

**Options:**
1. **Nuxt.js migration** (full SSR) - Major effort
2. **Vite SSR** - Moderate effort
3. **Prerendering** (recommended) - Low effort

```bash
# Using vite-plugin-ssr or prerender-spa-plugin
npm install vite-plugin-ssr
```

Prerender critical pages:
- Home, About, FAQ, Phenopackets list, Variants list, Publications list

### 4.2 Canonical URL Consistency

**Add to all pages:**
```html
<link rel="canonical" href="https://hnf1b.org/variants/NM_000458.4:c.544+1G>A">
```

Handle URL encoding consistently for variant IDs with special characters.

### 4.3 Internal Linking Strategy

**Create interconnection web:**
- Every phenopacket links to its variants
- Every variant links to its phenopackets
- Every publication links to phenopackets that cite it
- Add "Related variants" section
- Add "Related phenopackets" section

### 4.4 Page Load Performance

**Current:** Good (based on Lighthouse optimization work)
**Enhancements:**
- Image optimization (WebP format for 3D protein renders)
- Critical CSS extraction
- Resource hints (`<link rel="preload">` for D3.js, visualization data)

### 4.5 Mobile Optimization

Ensure all visualizations are responsive:
- Protein viewer touch controls
- Gene view pinch-zoom
- Table horizontal scroll on mobile

---

## Priority 5: External Authority Building (Impact: Very High, Effort: Ongoing)

### 5.1 Cross-Database Linking

**Outbound links (credibility signals):**
Add prominent links on variant pages to:
- ClinVar submission
- OMIM gene entry (189907)
- UniProt protein entry (P35680)
- Ensembl gene (ENSG00000275410)
- HGNC (11630)
- gnomAD

**Inbound links (authority building):**
Request listing on:
- OMIM (as a resource for HNF1B)
- GeneCards (external links section)
- Orphanet (ORPHA:2106 resources)
- RD-Connect (rare disease platform)
- Global Alliance for Genomics and Health (GA4GH) showcase
- NIH Genetic Testing Registry

### 5.2 Academic Publishing

**Publish a methods paper:**
- "HNF1B Database: A GA4GH Phenopackets-compliant resource for genotype-phenotype correlation"
- Target journals: Human Mutation, Database (Oxford), JAMIA

**Benefits:**
- Citable reference for researchers
- PubMed indexing
- Academic backlinks

### 5.3 GA4GH Beacon API Implementation

Implement the [GA4GH Beacon v2 API](https://beacon-project.io/):
- Enables federated queries across databases
- Increases visibility in genomics community
- Automatic listing in Beacon Network

```python
# Backend endpoint
@router.get("/beacon/v2/individuals")
async def beacon_query(variantType: str, referenceName: str, start: int, ...):
    # Return beacon response format
```

### 5.4 LOVD Integration

Either:
- A) Register as official HNF1B LOVD instance
- B) Export data to existing HNF1B LOVD (if one exists)
- C) Sync variants bidirectionally

### 5.5 Patient/Researcher Registry

**Add registration for:**
- Researchers wanting data updates
- Clinicians submitting cases
- Patients (with appropriate consent)

**Benefits:**
- Community building
- Email list for announcements (increases return visits)
- Demonstrates real-world usage

---

## Priority 6: Schema.org Enhancements (Impact: Medium, Effort: Low)

### 6.1 Per-Page Structured Data

**Variant pages:**
```json
{
  "@type": "MedicalGuideline",
  "guidelineSubject": {
    "@type": "MedicalCondition",
    "name": "HNF1B-related disorder"
  },
  "evidenceLevel": "Evidence from expert committee reports or opinions",
  "recommendationStrength": "Class I (strong)"
}
```

**Publication pages:**
```json
{
  "@type": "ScholarlyArticle",
  "headline": "[Publication title]",
  "author": [...],
  "datePublished": "2023-05-15",
  "publisher": {"@type": "Organization", "name": "Journal Name"},
  "identifier": {"@type": "PropertyValue", "propertyID": "PMID", "value": "12345678"}
}
```

### 6.2 HowTo Schema for Guides

```json
{
  "@type": "HowTo",
  "name": "How to Search for HNF1B Variants",
  "step": [
    {"@type": "HowToStep", "text": "Navigate to the Variants page"},
    {"@type": "HowToStep", "text": "Enter HGVS notation in search box"},
    ...
  ]
}
```

### 6.3 ItemList for Search Results

```json
{
  "@type": "ItemList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "item": {"@type": "Thing", "name": "c.544+1G>A"}},
    ...
  ]
}
```

---

## Priority 7: User Experience Enhancements (Impact: Medium, Effort: Medium)

### 7.1 Search Engine Within Site

**Enhance current search:**
- Autocomplete suggestions
- Typo tolerance ("rneal" → "renal")
- Search analytics (track failed queries)
- Faceted search refinement

### 7.2 Data Export Features

**Researchers want to download data:**
- CSV export for phenopackets
- JSON export (Phenopackets format)
- VCF export for variants
- Bibliography export (RIS, BibTeX, EndNote)

**Add prominent download buttons.**

### 7.3 Comparison Tools

- Compare two phenopackets side-by-side
- Compare phenotype frequency between variant types
- Compare this database's frequencies with published cohorts

### 7.4 API Documentation Page

**Create `/api-docs` public page:**
- Interactive API explorer (Swagger UI already at /docs)
- Code examples in Python, R, JavaScript
- Rate limiting information
- Authentication docs (for write access)

---

## Priority 8: Monitoring & Iteration (Impact: Ongoing, Effort: Low)

### 8.1 Google Search Console Setup

- Verify site ownership
- Submit sitemap
- Monitor indexing status
- Track search performance for key queries

### 8.2 Target Keyword Tracking

**Primary keywords to track:**
- "hnf1b database" (brand)
- "hnf1b variants"
- "hnf1b mutations"
- "mody5 database"
- "rcad syndrome database"
- "17q12 deletion database"
- "hnf1b phenotype"
- "hnf1b genotype phenotype"

**Tools:** Google Search Console, Ahrefs, SEMrush (free tiers available)

### 8.3 Analytics Implementation

If not present, add privacy-respecting analytics:
- Plausible Analytics (GDPR-compliant)
- Fathom Analytics
- Self-hosted Matomo

Track:
- Most visited variants
- Search queries
- Download events
- API usage

### 8.4 Regular Content Audits

**Monthly:**
- Update "last modified" dates where content changes
- Check for broken links
- Review search query performance

**Quarterly:**
- Add new publications
- Update statistics
- Publish news/updates

---

## Implementation Roadmap

### Phase 1: Quick Wins (Weeks 1-2)
- [ ] Dynamic sitemap generation
- [ ] FAQPage schema markup
- [ ] BreadcrumbList schema
- [ ] Per-page meta tags with vue-meta/unhead
- [ ] Medical review badges on content pages
- [ ] Google Search Console setup

### Phase 2: Content & Authority (Weeks 3-6)
- [ ] Educational content pages (/disease/*, /resources/*)
- [ ] Expert/author pages with credentials
- [ ] Enhanced variant detail pages
- [ ] Enhanced publication pages with abstracts
- [ ] DOI registration (Zenodo)

### Phase 3: Technical Excellence (Weeks 7-10)
- [ ] Prerendering for critical pages
- [ ] Beacon API implementation
- [ ] Data export features
- [ ] Public API documentation page

### Phase 4: Authority Outreach (Ongoing)
- [ ] Request listings from OMIM, GeneCards, Orphanet
- [ ] Submit methods paper manuscript
- [ ] GA4GH showcase application
- [ ] Build researcher/clinician registry

---

## Success Metrics

| Metric | Current | 6-Month Target | 12-Month Target |
|--------|---------|----------------|-----------------|
| Google index pages | ~10 | 500+ | 1,200+ |
| Organic search visitors/month | Unknown | 500 | 2,000 |
| Ranking: "hnf1b database" | Unknown | Top 5 | #1 |
| Ranking: "hnf1b variants" | Unknown | Top 10 | Top 3 |
| Backlinks from .edu/.gov | 0 | 5 | 15 |
| Citations in literature | 0 | 5 | 20 |
| API users | Unknown | 20 | 100 |

---

## Summary of Key Actions

1. **Fix sitemap** - Add all 1,100+ individual resource pages
2. **Add FAQ schema** - Enable rich snippets in search results
3. **Show expert credentials** - Critical for YMYL/medical content
4. **Create educational content** - Fill gaps vs. competitors
5. **Get a DOI** - Academic credibility signal
6. **Implement Beacon API** - Join GA4GH ecosystem
7. **Publish a paper** - Ultimate authority signal
8. **Build backlinks** - Request listings from authoritative databases

---

## References

- [Schema.org Medical Types](https://schema.org/docs/meddocs.html)
- [Healthcare Schema Markup Guide](https://healthcaresuccess.com/blog/seo/schema-markup-healthcare.html)
- [Google E-E-A-T Guidelines](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
- [GA4GH Beacon API](https://beacon-project.io/)
- [LOVD Platform](https://www.lovd.nl/)
- [GA4GH Phenopackets](https://phenopacket-schema.readthedocs.io/)

---

*Generated by Claude Code analysis of HNF1B Database codebase and competitive landscape research.*
