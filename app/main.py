# File: app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import (
    individuals,
    publications,
    variants,
    aggregations,
    proteins,
    genes,
    search,
)
from app.endpoints import auth

app = FastAPI(
    title="HNF1B-db API",
    description=(
        "The API powering the HNF1B-db website, including endpoints for "
        "individuals, publications, variants, aggregations, proteins, and genes."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(individuals.router, prefix="/api/individuals", tags=["Individuals"])
app.include_router(
    publications.router, prefix="/api/publications", tags=["Publications"]
)
app.include_router(variants.router, prefix="/api/variants", tags=["Variants"])
app.include_router(proteins.router, prefix="/api/proteins", tags=["Proteins"])
app.include_router(genes.router, prefix="/api/genes", tags=["Genes"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(
    aggregations.router, prefix="/api/aggregations", tags=["Aggregations"]
)
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
