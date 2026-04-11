"""Pydantic request/response models for the admin API.

Extracted from the old flat ``app/api/admin_endpoints.py`` during the
Wave 4 decomposition. Any module outside the admin sub-package that
needs one of these types should import it from here rather than from
the (now-deleted) flat module.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DataSyncStatus(BaseModel):
    """Status of a data synchronization category."""

    name: str = Field(..., description="Name of the data category")
    total: int = Field(..., description="Total items in database")
    synced: int = Field(..., description="Items with complete metadata")
    pending: int = Field(..., description="Items pending sync")
    last_sync: Optional[str] = Field(None, description="Last sync timestamp")


class SystemStatusResponse(BaseModel):
    """System status response with data sync information."""

    status: str = Field(default="healthy", description="Overall system status")
    timestamp: str = Field(..., description="Current server timestamp")
    database: dict = Field(..., description="Database statistics")
    sync_status: list[DataSyncStatus] = Field(
        ..., description="Status of various data sync operations"
    )


class SyncTaskResponse(BaseModel):
    """Response for sync task initiation."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Human-readable message")
    items_to_process: int = Field(..., description="Number of items to process")
    estimated_time_seconds: Optional[int] = Field(
        None, description="Estimated time to complete"
    )


class SyncProgressResponse(BaseModel):
    """Response for sync task progress."""

    task_id: str = Field(..., description="Task identifier")
    status: str = Field(
        ..., description="Task status (pending/running/completed/failed)"
    )
    progress: float = Field(..., description="Progress percentage (0-100)")
    processed: int = Field(..., description="Items processed")
    total: int = Field(..., description="Total items")
    errors: int = Field(default=0, description="Number of errors")
    started_at: Optional[str] = Field(None, description="Task start time")
    completed_at: Optional[str] = Field(None, description="Task completion time")
