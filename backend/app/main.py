"""HNF1B Phenopackets API v2 - Complete replacement with GA4GH Phenopackets."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import hpo_proxy, variant_validator_endpoint
from app.api import admin_endpoints, auth_endpoints
from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.core.mv_cache import init_mv_cache
from app.database import async_session_maker, engine
from app.ontology import routers as ontology_router
from app.phenopackets import clinical_endpoints
from app.phenopackets.routers import router as phenopackets_router
from app.publications import endpoints as publication_endpoints
from app.reference import router as reference_router
from app.search.routers import router as search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Database schema is now managed by Alembic migrations.
    Run 'uv run alembic upgrade head' to initialize/update the database schema.

    Initializes:
    - Redis cache connection (with in-memory fallback)
    - Materialized view availability cache (O(1) lookups)
    """
    # Application startup
    await init_cache()  # Initialize Redis cache

    # Initialize materialized view cache (checks availability once at startup)
    async with async_session_maker() as db:
        await init_mv_cache(db)

    yield
    # Cleanup on shutdown
    await close_cache()  # Close Redis connection
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="HNF1B Phenopackets API",
    description="GA4GH Phenopackets v2 compliant API for HNF1B disease data",
    version="2.0.0",
    lifespan=lifespan,
    openapi_url="/api/v2/openapi.json",  # OpenAPI spec at /api/v2/openapi.json
    docs_url="/api/v2/docs",
    redoc_url="/api/v2/redoc",
)

# Configure CORS with environment-based settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),  # Environment-specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Specific methods
    allow_headers=["Authorization", "Content-type"],  # Specific headers
)

# Include routers
app.include_router(phenopackets_router, prefix="/api/v2")
app.include_router(clinical_endpoints.router)
app.include_router(publication_endpoints.router)
app.include_router(auth_endpoints.router)
app.include_router(admin_endpoints.router)
app.include_router(hpo_proxy.router)
app.include_router(variant_validator_endpoint.router)
app.include_router(ontology_router.router, prefix="/api/v2")
app.include_router(reference_router.router, prefix="/api/v2")
app.include_router(search_router, prefix="/api/v2")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "HNF1B Phenopackets API",
        "version": "2.0.0",
        "description": "GA4GH Phenopackets v2 compliant API",
        "documentation": "/api/v2/docs",
        "endpoints": {
            "phenopackets": "/api/v2/phenopackets",
            "clinical": "/api/v2/clinical",
            "reference": "/api/v2/reference",
        },
        "standards": {
            "phenopackets": "GA4GH Phenopackets v2.0",
            "ontologies": {
                "HPO": "Human Phenotype Ontology",
                "MONDO": "Mondo Disease Ontology",
                "LOINC": "Logical Observation Identifiers Names and Codes",
            },
        },
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "phenopackets_schema": "2.0.0",
    }


# API information endpoint
@app.get("/api/v2/info")
async def api_info():
    """Get API information and capabilities."""
    return {
        "version": "2.0.0",
        "phenopackets_version": "2.0.0",
        "capabilities": {
            "search": True,
            "aggregation": True,
            "clinical_queries": True,
            "variant_interpretation": True,
            "audit_log": True,
        },
        "supported_ontologies": [
            {"id": "hpo", "name": "Human Phenotype Ontology", "version": "2024-01-01"},
            {"id": "mondo", "name": "Mondo Disease Ontology", "version": "2024-01-01"},
            {"id": "loinc", "name": "LOINC", "version": "2.76"},
            {"id": "omim", "name": "OMIM", "version": "2024-01-01"},
            {"id": "ncit", "name": "NCI Thesaurus", "version": "24.01"},
        ],
        "endpoints": [
            {
                "path": "/api/v2/phenopackets",
                "description": "Core phenopacket CRUD operations",
            },
            {
                "path": "/api/v2/phenopackets/search",
                "description": "Advanced phenopacket search",
            },
            {
                "path": "/api/v2/search/global",
                "description": "Global unified search",
            },
            {
                "path": "/api/v2/phenopackets/aggregate",
                "description": "Data aggregation endpoints",
            },
            {
                "path": "/api/v2/clinical",
                "description": "Clinical feature-specific queries",
            },
            {
                "path": "/api/v2/reference",
                "description": "Reference genome data (genes, transcripts, domains)",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
