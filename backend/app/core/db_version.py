"""Runtime resolution of the database schema (Alembic) version.

Exposes the migration revision currently *applied* to the database, the
revision *head* defined in the codebase, and whether they agree (drift
detection). All lookups are defensive: a failure returns ``None`` rather than
raising, so a version endpoint built on top of these never takes the API down.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_applied_revision(db: AsyncSession) -> str | None:
    """Return the Alembic revision currently applied to the database.

    Reads the single-row ``alembic_version`` table maintained by Alembic.
    Returns ``None`` if the table is absent (un-migrated DB) or unreadable.
    """
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        return result.scalar_one_or_none()
    except Exception:
        return None


def _find_alembic_ini() -> Path | None:
    """Locate ``alembic.ini`` by walking up from this module."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "alembic.ini"
        if candidate.is_file():
            return candidate
    return None


def get_head_revision() -> str | None:
    """Return the latest migration revision defined in the codebase (head).

    Resolved from the Alembic ``ScriptDirectory``. Returns ``None`` if Alembic
    is unavailable or the migration tree cannot be read. Multiple heads (an
    un-merged migration tree) are joined with commas so the drift is visible
    rather than hidden behind an exception.
    """
    ini = _find_alembic_ini()
    if ini is None:
        return None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(Config(str(ini)))
        heads = script.get_heads()
    except Exception:
        return None

    if len(heads) == 1:
        return heads[0]
    if heads:
        return ",".join(sorted(heads))
    return None
