"""PubMed API service with database caching.

This module provides publication metadata fetching from PubMed with:
- Database caching (90-day TTL)
- PMID validation (SQL injection prevention)
- Rate limiting handling
- Comprehensive error handling
- Provenance tracking
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import aiohttp
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Configuration
PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY")  # Optional but recommended
CACHE_TTL_DAYS = 90
API_VERSION = "2.0"  # E-utilities version

# Rate limiting based on API key presence
if PUBMED_API_KEY:
    MAX_REQUESTS_PER_SECOND = 10
    logger.info("PubMed API key configured: 10 req/sec limit")
else:
    MAX_REQUESTS_PER_SECOND = 3
    logger.warning("No PubMed API key: 3 req/sec limit")


# Custom exceptions
class PubMedError(Exception):
    """Base exception for PubMed API errors."""

    pass


class PubMedRateLimitError(PubMedError):
    """Rate limit exceeded (429)."""

    pass


class PubMedNotFoundError(PubMedError):
    """Publication not found (404)."""

    pass


class PubMedTimeoutError(PubMedError):
    """API request timed out."""

    pass


class PubMedAPIError(PubMedError):
    """General API error."""

    pass


def validate_pmid(pmid: str) -> str:
    """Validate and normalize PMID format.

    Security: Prevents SQL injection by validating format with regex.

    Args:
        pmid: PMID string (with or without PMID: prefix)

    Returns:
        Normalized PMID in format "PMID:12345678"

    Raises:
        ValueError: If PMID format is invalid

    Examples:
        >>> validate_pmid("30791938")
        'PMID:30791938'
        >>> validate_pmid("PMID:30791938")
        'PMID:30791938'
        >>> validate_pmid("PMID:999999999")  # Too long
        ValueError: Invalid PMID format: PMID:999999999. Expected PMID:12345678
        >>> validate_pmid("PMID:abc123")  # Non-numeric
        ValueError: Invalid PMID format: PMID:abc123. Expected PMID:12345678
    """
    # Add prefix if missing
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"

    # Validate format: PMID followed by 1-8 digits only
    # This prevents SQL injection attempts like "PMID:123; DROP TABLE users;"
    if not re.match(r"^PMID:\d{1,8}$", pmid):
        raise ValueError(
            f"Invalid PMID format: {pmid}. Expected PMID:12345678 (1-8 digits)"
        )

    return pmid


async def get_publication_metadata(
    pmid: str, db: AsyncSession, fetched_by: Optional[str] = "system"
) -> dict:
    """Fetch publication metadata with database caching.

    Flow:
    1. Validate PMID format (security)
    2. Check database cache (< 90 days old)
    3. If cache miss, fetch from PubMed API
    4. Store in cache and return

    Args:
        pmid: PubMed ID (format: PMID:12345678 or 12345678)
        db: Database session
        fetched_by: User or system identifier for audit trail

    Returns:
        dict: Publication metadata with keys:
            - pmid (str): Normalized PMID
            - title (str): Publication title
            - authors (list): List of author dicts [{name, affiliation}]
            - journal (str): Journal name
            - year (int): Publication year
            - doi (str|None): DOI if available
            - abstract (str|None): Abstract text if available
            - data_source (str): "PubMed"
            - fetched_at (datetime): Cache timestamp

    Raises:
        ValueError: If PMID format is invalid
        PubMedNotFoundError: If publication not found
        PubMedAPIError: If PubMed API fails
    """
    # Validate PMID format (prevents SQL injection)
    pmid = validate_pmid(pmid)
    logger.info(f"Fetching metadata for {pmid}", extra={"pmid": pmid})

    # Check cache
    cached = await _get_cached_metadata(pmid, db)
    if cached:
        logger.info(
            f"Cache hit for {pmid}",
            extra={
                "pmid": pmid,
                "cache_age_days": (datetime.now() - cached["fetched_at"]).days,
            },
        )
        return cached

    # Cache miss - fetch from PubMed
    logger.info(f"Cache miss for {pmid}, fetching from PubMed", extra={"pmid": pmid})
    metadata = await _fetch_from_pubmed(pmid)

    # Store in cache
    await _store_in_cache(metadata, db, fetched_by)
    logger.info(f"Cached metadata for {pmid}", extra={"pmid": pmid})

    return metadata


async def _get_cached_metadata(pmid: str, db: AsyncSession) -> Optional[dict]:
    """Check database cache for unexpired metadata.

    Args:
        pmid: Validated PMID in format PMID:12345678
        db: Database session

    Returns:
        dict|None: Cached metadata if found and not expired, None otherwise
    """
    query = text("""
        SELECT
            pmid,
            title,
            authors,
            journal,
            year,
            doi,
            abstract,
            data_source,
            fetched_at,
            fetched_by,
            api_version
        FROM publication_metadata
        WHERE pmid = :pmid
        AND fetched_at > NOW() - INTERVAL '90 days'
    """)

    result = await db.execute(query, {"pmid": pmid})
    row = result.fetchone()

    if row:
        return {
            "pmid": row.pmid,
            "title": row.title,
            "authors": row.authors,  # Already JSONB
            "journal": row.journal,
            "year": row.year,
            "doi": row.doi,
            "abstract": row.abstract,
            "data_source": row.data_source,
            "fetched_at": row.fetched_at,
            "fetched_by": row.fetched_by,
            "api_version": row.api_version,
        }

    return None


async def _fetch_from_pubmed(pmid: str) -> dict:
    """Fetch metadata from PubMed E-utilities API.

    Args:
        pmid: Validated PMID in format PMID:12345678

    Returns:
        dict: Publication metadata

    Raises:
        PubMedRateLimitError: If rate limit exceeded (429)
        PubMedNotFoundError: If PMID not found
        PubMedTimeoutError: If request times out
        PubMedAPIError: For other API errors
    """
    pmid_number = pmid.replace("PMID:", "")

    # Build URL with optional API key
    params = {
        "db": "pubmed",
        "id": pmid_number,
        "retmode": "json",
        "rettype": "abstract",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY

    try:
        async with aiohttp.ClientSession() as session:
            # 5 second timeout for API call
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.get(
                PUBMED_API, params=params, timeout=timeout
            ) as response:
                # Handle rate limiting
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.error(
                        f"Rate limit exceeded for {pmid}",
                        extra={"pmid": pmid, "retry_after": retry_after},
                    )
                    raise PubMedRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds"
                    )

                # Handle non-200 responses
                if response.status != 200:
                    logger.error(
                        f"PubMed API returned {response.status} for {pmid}",
                        extra={"pmid": pmid, "status": response.status},
                    )
                    raise PubMedAPIError(
                        f"PubMed API returned status {response.status}"
                    )

                data = await response.json()

                # Check if PMID exists in response
                result = data.get("result", {})
                if pmid_number not in result:
                    logger.warning(
                        f"PMID {pmid} not found in PubMed", extra={"pmid": pmid}
                    )
                    raise PubMedNotFoundError(f"PMID {pmid} not found in PubMed")

                pub_data = result[pmid_number]

                # Parse authors (preserve order with JSONB)
                authors = []
                for author in pub_data.get("authors", []):
                    authors.append(
                        {
                            "name": author.get("name", ""),
                            "affiliation": author.get("affinfo", ""),
                        }
                    )

                # Extract metadata
                metadata = {
                    "pmid": pmid,
                    "title": pub_data.get("title", "Unknown"),
                    "authors": authors,
                    "journal": pub_data.get("fulljournalname", ""),
                    "year": int(pub_data.get("pubdate", "0")[:4])
                    if pub_data.get("pubdate")
                    else None,
                    "doi": _extract_doi(pub_data),
                    "abstract": _extract_abstract(pub_data),
                    "data_source": "PubMed",
                    "fetched_at": datetime.now(),
                }

                logger.info(
                    f"Successfully fetched metadata for {pmid}",
                    extra={"pmid": pmid, "title": metadata["title"][:50]},
                )

                return metadata

    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {pmid} from PubMed", extra={"pmid": pmid})
        raise PubMedTimeoutError(f"Timeout fetching {pmid}")
    except aiohttp.ClientError as e:
        logger.error(
            f"Network error fetching {pmid}: {e}", extra={"pmid": pmid, "error": str(e)}
        )
        raise PubMedAPIError(f"Network error: {e}")


def _extract_doi(pub_data: dict) -> Optional[str]:
    """Extract DOI from PubMed article IDs."""
    for article_id in pub_data.get("articleids", []):
        if article_id.get("idtype") == "doi":
            return article_id.get("value")
    return None


def _extract_abstract(pub_data: dict) -> Optional[str]:
    """Extract abstract text from PubMed data."""
    # PubMed may not include abstracts in esummary
    # Would need efetch for full abstract
    return None  # Placeholder for now


async def _store_in_cache(
    metadata: dict, db: AsyncSession, fetched_by: Optional[str] = "system"
) -> None:
    """Store publication metadata in database cache.

    Args:
        metadata: Publication metadata dict
        db: Database session
        fetched_by: User or system identifier
    """
    query = text("""
        INSERT INTO publication_metadata (
            pmid, title, authors, journal, year, doi, abstract,
            data_source, fetched_by, fetched_at, api_version
        )
        VALUES (
            :pmid, :title, :authors, :journal, :year, :doi, :abstract,
            :data_source, :fetched_by, :fetched_at, :api_version
        )
        ON CONFLICT (pmid) DO UPDATE SET
            title = EXCLUDED.title,
            authors = EXCLUDED.authors,
            journal = EXCLUDED.journal,
            year = EXCLUDED.year,
            doi = EXCLUDED.doi,
            abstract = EXCLUDED.abstract,
            fetched_at = EXCLUDED.fetched_at,
            fetched_by = EXCLUDED.fetched_by
    """)

    await db.execute(
        query,
        {
            "pmid": metadata["pmid"],
            "title": metadata["title"],
            "authors": json.dumps(
                metadata["authors"]
            ),  # Convert to JSON string for JSONB column
            "journal": metadata["journal"],
            "year": metadata["year"],
            "doi": metadata["doi"],
            "abstract": metadata["abstract"],
            "data_source": metadata["data_source"],
            "fetched_by": fetched_by,
            "fetched_at": metadata["fetched_at"],
            "api_version": API_VERSION,
        },
    )

    await db.commit()
