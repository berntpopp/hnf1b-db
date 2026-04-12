"""Seed state='published' + one head-published revision row per existing phenopacket.

Revision ID: 20260412_0003
Revises: 20260412_0002
Create Date: 2026-04-12

Part of Wave 7 D.1. See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.3.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260412_0003"
down_revision = "20260412_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Ensure a `system` user exists.
    conn.execute(
        sa.text(
            """
            INSERT INTO users (
              username, email, hashed_password, role,
              is_active, is_verified, full_name, created_at
            )
            VALUES (
              'system', 'system@hnf1b-db.local',
              '$argon2id$v=19$m=19456,t=2,p=1$0000000000000000$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
              'admin',
              FALSE, TRUE, 'System',
              NOW()
            )
            ON CONFLICT (username) DO NOTHING
            """
        )
    )
    system_id = conn.execute(
        sa.text("SELECT id FROM users WHERE username='system'")
    ).scalar_one()

    # 2. For every existing row: insert a revision row, then set head pointer + state.
    conn.execute(
        sa.text(
            """
            INSERT INTO phenopacket_revisions (
              record_id, revision_number, state, content_jsonb, change_patch,
              change_reason, actor_id, from_state, to_state, is_head_published, created_at
            )
            SELECT
              id, revision, 'published', phenopacket, NULL,
              'Migrated from pre-D.1 data model', :sys, NULL, 'published', TRUE, NOW()
            FROM phenopackets
            """
        ),
        {"sys": system_id},
    )

    conn.execute(
        sa.text(
            """
            UPDATE phenopackets p
            SET
              state = 'published',
              head_published_revision_id = r.id,
              draft_owner_id = NULL,
              editing_revision_id = NULL
            FROM phenopacket_revisions r
            WHERE r.record_id = p.id AND r.is_head_published = TRUE
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE phenopackets
            SET state='draft', head_published_revision_id=NULL,
                editing_revision_id=NULL, draft_owner_id=NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM phenopacket_revisions
            WHERE change_reason='Migrated from pre-D.1 data model'
            """
        )
    )
