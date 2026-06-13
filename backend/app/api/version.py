"""Version endpoint: application + database schema versions.

Exposes the single-sourced application version (from ``pyproject.toml``) and
the live Alembic schema revision (applied vs. codebase head, with an in-sync
flag for drift detection). Read-only and unauthenticated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_version import get_applied_revision, get_head_revision
from app.core.version import API_PATH_VERSION, APP_VERSION, PHENOPACKET_SCHEMA_VERSION
from app.database import get_db

router = APIRouter(tags=["meta"])


class VersionResponse(BaseModel):
    """Application and database schema version information."""

    api_version: str = Field(
        ...,
        description=(
            "Application version (semver; beta 0.X.Y), single-sourced from "
            "pyproject.toml — never hardcoded in application code."
        ),
        examples=["0.1.1"],
    )
    api_path_version: str = Field(
        ...,
        description="Major version of the REST API URL contract (the /api/v2 prefix).",
        examples=["v2"],
    )
    phenopacket_schema_version: str = Field(
        ...,
        description="GA4GH Phenopackets schema version the API conforms to.",
        examples=["2.0.0"],
    )
    db_schema_revision: str | None = Field(
        None,
        description=(
            "Alembic migration revision currently applied to the database, or "
            "null if it cannot be determined."
        ),
    )
    db_schema_head: str | None = Field(
        None,
        description=(
            "Latest Alembic migration revision defined in the codebase (head), "
            "or null if it cannot be determined."
        ),
    )
    db_schema_in_sync: bool | None = Field(
        None,
        description=(
            "True when the applied DB revision matches the codebase head; null "
            "if either revision is unknown."
        ),
    )


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Get API and database schema versions",
    description=(
        "Returns the application version (single-sourced from pyproject.toml) "
        "and the live database schema revision, including whether the applied "
        "migration matches the codebase head (drift detection)."
    ),
)
async def get_version(db: AsyncSession = Depends(get_db)) -> VersionResponse:
    """Report application and database schema versions."""
    applied = await get_applied_revision(db)
    head = get_head_revision()
    in_sync = applied == head if applied is not None and head is not None else None
    return VersionResponse(
        api_version=APP_VERSION,
        api_path_version=API_PATH_VERSION,
        phenopacket_schema_version=PHENOPACKET_SCHEMA_VERSION,
        db_schema_revision=applied,
        db_schema_head=head,
        db_schema_in_sync=in_sync,
    )
