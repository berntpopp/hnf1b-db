# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.endpoints import individuals, publications, variants

app = FastAPI(
    title="HNF1B-db API",
    description="The API powering the HNF1B-db website and providing endpoints for individuals, reports, publications, and variants.",
    version="0.1.0"
)

# Configure CORS to allow requests from everywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.include_router(individuals.router, prefix="/api/individuals", tags=["Individuals"])
app.include_router(publications.router, prefix="/api/publications", tags=["Publications"])
app.include_router(variants.router, prefix="/api/variants", tags=["Variants"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
