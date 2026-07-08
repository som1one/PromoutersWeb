from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from promouters.models.enums import RoleCode
from promouters.models.users import User

MANAGEABLE_ROLE_CODES_BY_BRANCH_MANAGER = {
    RoleCode.AD_DIRECTOR,
    RoleCode.DISPATCHER,
    RoleCode.MASTER,
    RoleCode.PROMOTER,
}
ROUTE_MANAGER_ROLE_CODES = {
    RoleCode.OWNER,
    RoleCode.BRANCH_MANAGER,
    RoleCode.AD_DIRECTOR,
    RoleCode.DISPATCHER,
}


def get_role_code(user: User) -> RoleCode:
    if user.role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role is not configured")

    try:
        return RoleCode(user.role.code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role") from exc


def is_owner(user: User) -> bool:
    return get_role_code(user) == RoleCode.OWNER


def is_branch_manager(user: User) -> bool:
    return get_role_code(user) == RoleCode.BRANCH_MANAGER


def is_ad_director(user: User) -> bool:
    return get_role_code(user) == RoleCode.AD_DIRECTOR


def is_route_manager(user: User) -> bool:
    return get_role_code(user) in ROUTE_MANAGER_ROLE_CODES


def require_roles(user: User, allowed_roles: set[RoleCode]) -> RoleCode:
    role_code = get_role_code(user)
    if role_code not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return role_code


def require_owner(user: User) -> None:
    require_roles(user, {RoleCode.OWNER})


def require_owner_or_branch_manager(user: User) -> RoleCode:
    return require_roles(user, {RoleCode.OWNER, RoleCode.BRANCH_MANAGER})


def require_route_manager(user: User) -> RoleCode:
    return require_roles(user, ROUTE_MANAGER_ROLE_CODES)


def require_branch_assignment(user: User) -> UUID:
    if user.branch_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User branch is not configured")
    return user.branch_id


def ensure_same_branch(user: User, branch_id: UUID | None) -> None:
    if is_owner(user):
        return

    user_branch_id = require_branch_assignment(user)
    if branch_id != user_branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-branch access is forbidden")


def can_assign_role(actor: User, target_role_code: RoleCode) -> bool:
    actor_role_code = get_role_code(actor)
    if actor_role_code == RoleCode.OWNER:
        return True
    if actor_role_code == RoleCode.BRANCH_MANAGER:
        return target_role_code in MANAGEABLE_ROLE_CODES_BY_BRANCH_MANAGER
    if actor_role_code == RoleCode.AD_DIRECTOR:
        # Директор по рекламе может только СОЗДАВАТЬ промоутеров
        # (редактирование и удаление ему недоступны — отдельными маршрутами).
        return target_role_code == RoleCode.PROMOTER
    return False


def can_manage_user(actor: User, target: User) -> bool:
    actor_role_code = get_role_code(actor)
    target_role_code = get_role_code(target)

    if actor_role_code == RoleCode.OWNER:
        return True

    if actor_role_code != RoleCode.BRANCH_MANAGER:
        return False

    if target.branch_id != require_branch_assignment(actor):
        return False

    return target_role_code in MANAGEABLE_ROLE_CODES_BY_BRANCH_MANAGER
