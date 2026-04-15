"""Mentionable-users autocomplete endpoint (D.2 §5.7)."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_curator
from app.comments.schemas import MentionableUserOut
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/mentionable", response_model=Dict[str, List[MentionableUserOut]])
async def get_mentionable_users(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_curator),
) -> Dict[str, List[MentionableUserOut]]:
    """Autocomplete for @-mentions (curator/admin, active users only)."""
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_(("curator", "admin")),
            User.username.ilike(f"{q}%"),
        )
        .order_by(User.username.asc())
        .limit(20)
    )
    users = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            MentionableUserOut(id=u.id, username=u.username, display_name=u.full_name)
            for u in users
        ]
    }
