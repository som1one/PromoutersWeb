"""Add role codes, seed system roles, and scope audit logs by branch."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_role_scope"
down_revision = "0002_sms_codes"
branch_labels = None
depends_on = None


SYSTEM_ROLES = [
    {
        "code": "owner",
        "name": "Owner",
        "description": "Full cross-branch access and administration.",
    },
    {
        "code": "branch_manager",
        "name": "Branch Manager",
        "description": "Manages users and data within a single branch.",
    },
    {
        "code": "ad_director",
        "name": "Advertising Director",
        "description": "Manages advertising workflows within a branch.",
    },
    {
        "code": "master",
        "name": "Master",
        "description": "Operational role for field execution support.",
    },
    {
        "code": "promoter",
        "name": "Promoter",
        "description": "Field promoter role with limited branch access.",
    },
]

ROLE_NAME_TO_CODE = {
    "owner": "owner",
    "branchmanager": "branch_manager",
    "branch_manager": "branch_manager",
    "manager": "branch_manager",
    "managerbranch": "branch_manager",
    "branch manager": "branch_manager",
    "addirector": "ad_director",
    "ad_director": "ad_director",
    "advertisingdirector": "ad_director",
    "directorbyadvertising": "ad_director",
    "master": "master",
    "promoter": "promoter",
}


def normalize_role_name(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace("-", "")
        .replace(" ", "")
        .replace("__", "_")
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("roles", sa.Column("code", sa.String(length=50), nullable=True))
    op.add_column("audit_logs", sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_audit_logs_branch_id_branches",
        "audit_logs",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_audit_logs_branch_id", "audit_logs", ["branch_id"])

    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String(length=50)),
        sa.column("name", sa.String(length=50)),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
    )
    users_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("branch_id", postgresql.UUID(as_uuid=True)),
        sa.column("is_superuser", sa.Boolean()),
    )

    existing_roles = list(bind.execute(sa.select(roles_table.c.id, roles_table.c.name)))
    canonical_role_ids: dict[str, uuid.UUID] = {}

    for role_id, role_name in existing_roles:
        normalized_name = normalize_role_name(role_name)
        mapped_code = ROLE_NAME_TO_CODE.get(normalized_name)

        if mapped_code is None:
            bind.execute(
                roles_table.update()
                .where(roles_table.c.id == role_id)
                .values(code=f"legacy_{uuid.uuid4().hex[:12]}", is_system=False)
            )
            continue

        if mapped_code not in canonical_role_ids:
            system_role = next(role for role in SYSTEM_ROLES if role["code"] == mapped_code)
            bind.execute(
                roles_table.update()
                .where(roles_table.c.id == role_id)
                .values(
                    code=system_role["code"],
                    name=system_role["name"],
                    description=system_role["description"],
                    is_system=True,
                )
            )
            canonical_role_ids[mapped_code] = role_id
            continue

        canonical_role_id = canonical_role_ids[mapped_code]
        bind.execute(
            users_table.update()
            .where(users_table.c.role_id == role_id)
            .values(role_id=canonical_role_id)
        )
        bind.execute(
            roles_table.update()
            .where(roles_table.c.id == role_id)
            .values(code=f"legacy_{uuid.uuid4().hex[:12]}", is_system=False)
        )

    current_roles = {
        row.code: row.id
        for row in bind.execute(sa.select(roles_table.c.id, roles_table.c.code).where(roles_table.c.code.is_not(None)))
    }

    for system_role in SYSTEM_ROLES:
        if system_role["code"] in current_roles:
            continue

        role_id = uuid.uuid4()
        bind.execute(
            roles_table.insert().values(
                id=role_id,
                code=system_role["code"],
                name=system_role["name"],
                description=system_role["description"],
                is_system=True,
            )
        )
        current_roles[system_role["code"]] = role_id

    owner_role_id = current_roles["owner"]
    promoter_role_id = current_roles["promoter"]

    bind.execute(
        users_table.update()
        .where(users_table.c.is_superuser.is_(True))
        .values(role_id=owner_role_id, is_superuser=True)
    )

    system_role_ids = tuple(current_roles.values())
    bind.execute(
        users_table.update()
        .where(
            users_table.c.is_superuser.is_(False),
            users_table.c.role_id.not_in(system_role_ids),
        )
        .values(role_id=promoter_role_id, is_superuser=False)
    )
    bind.execute(
        users_table.update()
        .where(users_table.c.role_id == current_roles["branch_manager"])
        .values(is_superuser=False)
    )
    bind.execute(
        users_table.update()
        .where(users_table.c.role_id == current_roles["ad_director"])
        .values(is_superuser=False)
    )
    bind.execute(
        users_table.update()
        .where(users_table.c.role_id == current_roles["master"])
        .values(is_superuser=False)
    )
    bind.execute(
        users_table.update()
        .where(users_table.c.role_id == current_roles["promoter"])
        .values(is_superuser=False)
    )

    op.create_unique_constraint("uq_roles_code", "roles", ["code"])
    op.alter_column("roles", "code", nullable=False)


def downgrade() -> None:
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.drop_index("ix_audit_logs_branch_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_branch_id_branches", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "branch_id")
    op.drop_column("roles", "code")
