"""SEO Sitemap Generation Endpoints.

Generates dynamic XML sitemaps for improved search engine discoverability.
Critical for making individual variants/mutations findable via Google.

Implements:
- sitemap-index.xml - Master sitemap index
- sitemap-static.xml - Static pages
- sitemap-variants.xml - All variant pages (mutations)
- sitemap-phenopackets.xml - All phenopacket pages
- sitemap-publications.xml - All publication pages

@see https://www.sitemaps.org/protocol.html
"""

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.phenopackets.models import Phenopacket

router = APIRouter(tags=["seo"])

# Base URL for the site - should match deployment
BASE_URL = "https://hnf1b.org"


def xml_escape(text: str) -> str:
    """Escape special characters for XML."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_lastmod(dt: datetime | None) -> str:
    """Format datetime for sitemap lastmod element."""
    if not dt:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d")


@router.get("/sitemap-index.xml", response_class=Response)
async def sitemap_index() -> Response:
    """Generate sitemap index pointing to individual sitemaps.

    Returns:
        XML sitemap index
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{BASE_URL}/api/v2/seo/sitemap-static.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{BASE_URL}/api/v2/seo/sitemap-variants.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{BASE_URL}/api/v2/seo/sitemap-phenopackets.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>{BASE_URL}/api/v2/seo/sitemap-publications.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
</sitemapindex>"""

    return Response(content=xml, media_type="application/xml")


@router.get("/sitemap-static.xml", response_class=Response)
async def sitemap_static() -> Response:
    """Generate sitemap for static pages.

    Returns:
        XML sitemap for static pages
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    static_pages = [
        {"loc": "/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": "/phenopackets", "priority": "0.9", "changefreq": "daily"},
        {"loc": "/variants", "priority": "0.9", "changefreq": "daily"},
        {"loc": "/publications", "priority": "0.9", "changefreq": "weekly"},
        {"loc": "/aggregations", "priority": "0.8", "changefreq": "weekly"},
        {"loc": "/search", "priority": "0.7", "changefreq": "weekly"},
        {"loc": "/about", "priority": "0.7", "changefreq": "monthly"},
        {"loc": "/faq", "priority": "0.7", "changefreq": "monthly"},
    ]

    urls = []
    for page in static_pages:
        urls.append(f"""  <url>
    <loc>{BASE_URL}{page['loc']}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    return Response(content=xml, media_type="application/xml")


@router.get("/sitemap-variants.xml", response_class=Response)
async def sitemap_variants(db: AsyncSession = Depends(get_db)) -> Response:
    """Generate sitemap for all variant pages.

    This is critical for mutation discoverability - each variant gets its own
    URL that can be indexed by search engines, making mutations findable by
    their HGVS notation, protein change, etc.

    Returns:
        XML sitemap for variant pages
    """
    # Get all unique variants from phenopackets
    # Query the JSONB to extract variant information
    query = select(
        Phenopacket.phenopacket,
        Phenopacket.updated_at,
    ).where(Phenopacket.deleted_at.is_(None))

    result = await db.execute(query)
    records = result.all()

    # Extract unique variants
    variants_seen: dict[str, datetime] = {}

    for record in records:
        phenopacket = record.phenopacket
        updated_at = record.updated_at

        # Navigate to variants in phenopacket structure
        interpretations = phenopacket.get("interpretations", [])
        for interp in interpretations:
            diagnosis = interp.get("diagnosis", {})
            genomic_interps = diagnosis.get("genomicInterpretations", [])
            for gi in genomic_interps:
                var_interp = gi.get("variantInterpretation", {})
                var_desc = var_interp.get("variationDescriptor", {})

                # Get variant ID
                variant_id = var_desc.get("id")
                if variant_id and variant_id not in variants_seen:
                    variants_seen[variant_id] = updated_at
                elif variant_id and updated_at:
                    min_dt = datetime.min.replace(tzinfo=timezone.utc)
                    if updated_at > variants_seen.get(variant_id, min_dt):
                        variants_seen[variant_id] = updated_at

    # Generate URL entries
    urls = []
    for variant_id, updated_at in variants_seen.items():
        # URL-encode the variant ID (may contain special characters like :, +, >)
        encoded_id = quote(variant_id, safe="")
        lastmod = format_lastmod(updated_at)

        urls.append(f"""  <url>
    <loc>{BASE_URL}/variants/{encoded_id}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    return Response(content=xml, media_type="application/xml")


@router.get("/sitemap-phenopackets.xml", response_class=Response)
async def sitemap_phenopackets(db: AsyncSession = Depends(get_db)) -> Response:
    """Generate sitemap for all phenopacket pages.

    Returns:
        XML sitemap for phenopacket pages
    """
    query = select(
        Phenopacket.phenopacket_id,
        Phenopacket.updated_at,
    ).where(Phenopacket.deleted_at.is_(None))

    result = await db.execute(query)
    records = result.all()

    urls = []
    for record in records:
        encoded_id = quote(str(record.phenopacket_id), safe="")
        lastmod = format_lastmod(record.updated_at)

        urls.append(f"""  <url>
    <loc>{BASE_URL}/phenopackets/{encoded_id}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    return Response(content=xml, media_type="application/xml")


@router.get("/sitemap-publications.xml", response_class=Response)
async def sitemap_publications(db: AsyncSession = Depends(get_db)) -> Response:
    """Generate sitemap for all publication pages.

    Returns:
        XML sitemap for publication pages
    """
    # Extract unique PMIDs from phenopackets
    query = select(
        Phenopacket.phenopacket,
    ).where(Phenopacket.deleted_at.is_(None))

    result = await db.execute(query)
    records = result.all()

    pmids_seen: set[str] = set()

    for record in records:
        phenopacket = record.phenopacket
        # Extract PMIDs from metaData.externalReferences
        metadata = phenopacket.get("metaData", {})
        external_refs = metadata.get("externalReferences", [])
        for ref in external_refs:
            ref_id = ref.get("id", "")
            if ref_id.startswith("PMID:"):
                pmid = ref_id.replace("PMID:", "")
                pmids_seen.add(pmid)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = []
    for pmid in sorted(pmids_seen):
        urls.append(f"""  <url>
    <loc>{BASE_URL}/publications/{pmid}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    return Response(content=xml, media_type="application/xml")
