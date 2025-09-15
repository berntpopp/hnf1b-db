"""HNF1B Phenopackets API v2 - Complete replacement with GA4GH Phenopackets."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.phenopackets import clinical_endpoints, endpoints
from app.phenopackets.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup on shutdown
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="HNF1B Phenopackets API",
    description="GA4GH Phenopackets v2 compliant API for HNF1B disease data",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/v2/docs",
    redoc_url="/api/v2/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(endpoints.router)
app.include_router(clinical_endpoints.router)


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
                "path": "/api/v2/phenopackets/aggregate",
                "description": "Data aggregation endpoints",
            },
            {
                "path": "/api/v2/clinical",
                "description": "Clinical feature-specific queries",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )