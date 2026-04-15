"""Unit tests: new ORM fields on Phenopacket + PhenopacketRevision + Pydantic schemas.

Wave 7 D.1 Tasks 4 + 5.
See .planning/specs/2026-04-12-wave-7-d1-state-machine-design.md §4 and §7.3.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.models.user import User
from app.phenopackets.models import Phenopacket, PhenopacketRevision

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_system_user(db_session: AsyncSession) -> User:
    """Create a minimal 'system' user for actor_id FKs in revision tests."""
    user = User(
        username="system",
        email="system@hnf1b-db.local",
        hashed_password=get_password_hash("!SystemAcct0Disabled!"),
        role="admin",
        is_active=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Task 4: ORM model tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phenopacket_has_state_fields(db_session: AsyncSession) -> None:
    """Phenopacket ORM model exposes state, editing_revision_id, etc."""
    pp = Phenopacket(
        phenopacket_id="test-1",
        phenopacket={"id": "test-1"},
        state="draft",
        revision=1,
    )
    db_session.add(pp)
    await db_session.commit()
    await db_session.refresh(pp)
    assert pp.state == "draft"
    assert pp.editing_revision_id is None
    assert pp.head_published_revision_id is None
    assert pp.draft_owner_id is None


@pytest.mark.asyncio
async def test_revision_row_roundtrip(
    db_session: AsyncSession, seeded_system_user: User
) -> None:
    """PhenopacketRevision can be inserted and queried."""
    pp = Phenopacket(
        phenopacket_id="test-2",
        phenopacket={},
        state="draft",
        revision=1,
    )
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=1,
        state="draft",
        content_jsonb={"x": 1},
        change_reason="init",
        actor_id=seeded_system_user.id,
        from_state=None,
        to_state="draft",
        is_head_published=False,
    )
    db_session.add(rev)
    await db_session.commit()

    result = await db_session.execute(
        select(PhenopacketRevision).where(PhenopacketRevision.record_id == pp.id)
    )
    rev2 = result.scalar_one()
    assert rev2.content_jsonb == {"x": 1}
    assert rev2.is_head_published is False


@pytest.mark.asyncio
async def test_phenopacket_head_published_revision_pointer(
    db_session: AsyncSession, seeded_system_user: User
) -> None:
    """Phenopacket.head_published_revision_id FK points to a revision row."""
    pp = Phenopacket(
        phenopacket_id="test-3",
        phenopacket={"id": "test-3"},
        state="published",
        revision=1,
    )
    db_session.add(pp)
    await db_session.flush()

    rev = PhenopacketRevision(
        record_id=pp.id,
        revision_number=1,
        state="published",
        content_jsonb={"id": "test-3"},
        change_reason="initial publish",
        actor_id=seeded_system_user.id,
        from_state=None,
        to_state="published",
        is_head_published=True,
    )
    db_session.add(rev)
    await db_session.flush()

    pp.head_published_revision_id = rev.id
    await db_session.commit()
    await db_session.refresh(pp)

    assert pp.head_published_revision_id == rev.id
    assert pp.state == "published"


# ---------------------------------------------------------------------------
# Task 5: Pydantic schema tests
# ---------------------------------------------------------------------------


from app.phenopackets.models import (  # noqa: E402
    PhenopacketResponse,
    RevisionResponse,
    TransitionRequest,
)


def test_phenopacket_response_has_state_fields() -> None:
    """PhenopacketResponse includes the new Wave 7 state fields."""
    resp = PhenopacketResponse(
        id="00000000-0000-0000-0000-000000000001",
        phenopacket_id="x",
        version="2.0",
        schema_version="2.0.0",
        phenopacket={},
        revision=1,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        state="published",
        head_published_revision_id=10,
        editing_revision_id=None,
        draft_owner_id=None,
        draft_owner_username=None,
    )
    assert resp.state == "published"
    assert resp.head_published_revision_id == 10
    assert resp.editing_revision_id is None
    assert resp.draft_owner_id is None
    assert resp.draft_owner_username is None


def test_transition_request_validation() -> None:
    """TransitionRequest validates to_state and reason correctly."""
    r = TransitionRequest(to_state="in_review", reason="please review", revision=1)
    assert r.to_state == "in_review"
    assert r.reason == "please review"
    assert r.revision == 1

    with pytest.raises(ValueError):
        # reason min_length=1 violated by empty string
        TransitionRequest(to_state="in_review", reason="", revision=1)


def test_transition_request_rejects_bad_state() -> None:
    """TransitionRequest rejects states not in the Literal enum."""
    with pytest.raises(ValueError):
        TransitionRequest(to_state="not_a_state", reason="x", revision=1)  # type: ignore[arg-type]


def test_revision_response_schema() -> None:
    """RevisionResponse accepts a full set of fields."""
    from datetime import datetime

    rr = RevisionResponse(
        id=1,
        record_id="00000000-0000-0000-0000-000000000001",
        phenopacket_id="pp-001",
        revision_number=1,
        state="published",
        from_state=None,
        to_state="published",
        is_head_published=True,
        change_reason="Migrated from pre-D.1 data model",
        actor_id=1,
        actor_username="system",
        change_patch=None,
        created_at=datetime(2026, 1, 1, 0, 0, 0),
        content_jsonb={"id": "pp-001"},
    )
    assert rr.id == 1
    assert rr.is_head_published is True
    assert rr.actor_username == "system"
