"""Add role text column to users for PJ2 bot compatibility.

The VK/Telegram bots (PythonProject2) query ``users.role`` as a plain text
column (e.g. 'master', 'owner', 'director'). The web backend uses
``users.role_id`` FK → ``roles`` table. This migration adds a denormalized
``role`` text column populated from ``roles.code`` so both codebases can
coexist on the same database.

A trigger keeps ``role`` in sync when ``role_id`` is updated.
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_role_col_pj2"
down_revision = "0008_add_vk_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable role column first
    op.add_column("users", sa.Column("role", sa.String(50), nullable=True))

    # Populate from roles.code
    op.execute("""
        UPDATE users
        SET role = roles.code
        FROM roles
        WHERE users.role_id = roles.id
    """)

    # Set default for any nulls
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")

    # Create trigger function to auto-sync role on role_id change
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_user_role_from_role_id()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.role_id IS DISTINCT FROM OLD.role_id THEN
                SELECT code INTO NEW.role FROM roles WHERE id = NEW.role_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_sync_user_role
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION sync_user_role_from_role_id();
    """)

    # Also trigger on INSERT
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_user_role_on_insert()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.role IS NULL AND NEW.role_id IS NOT NULL THEN
                SELECT code INTO NEW.role FROM roles WHERE id = NEW.role_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_sync_user_role_insert
        BEFORE INSERT ON users
        FOR EACH ROW
        EXECUTE FUNCTION sync_user_role_on_insert();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_user_role_insert ON users")
    op.execute("DROP FUNCTION IF EXISTS sync_user_role_on_insert()")
    op.execute("DROP TRIGGER IF EXISTS trg_sync_user_role ON users")
    op.execute("DROP FUNCTION IF EXISTS sync_user_role_from_role_id()")
    op.drop_column("users", "role")
