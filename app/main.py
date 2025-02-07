# app/main.py
from fastapi import FastAPI
from app.endpoints import individuals, reports, publications, variants

app = FastAPI(
    title="HNF1B-db API",
    description="The API powering the HNF1B-db website and providing endpoints for individuals, reports, publications, and variants.",
    version="0.1.0"
)

app.include_router(individuals.router, prefix="/api/individuals", tags=["Individuals"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(publications.router, prefix="/api/publications", tags=["Publications"])
app.include_router(variants.router, prefix="/api/variants", tags=["Variants"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
