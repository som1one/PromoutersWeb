from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from promouters.models.enums import RoleCode
from promouters.models.users import Role
from promouters.schemas.roles import RoleRead


def role_query() -> Select[tuple[Role]]:
    return select(Role).where(Role.is_system.is_(True))


def to_role_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def list_roles(db: Session, *, codes: set[RoleCode] | None = None) -> list[Role]:
    stmt = role_query().order_by(Role.created_at.asc())
    if codes is not None:
        stmt = stmt.where(Role.code.in_([code.value for code in codes]))
    return list(db.scalars(stmt))
