from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.enums import RoleCode
from promouters.models.users import User
from promouters.schemas.roles import RoleRead
from promouters.services.access import is_branch_manager, is_owner
from promouters.services.roles import list_roles, to_role_read

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleRead])
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RoleRead]:
    if is_owner(current_user):
        roles = list_roles(db)
    elif is_branch_manager(current_user):
        roles = list_roles(
            db,
            codes={RoleCode.AD_DIRECTOR, RoleCode.MASTER, RoleCode.PROMOTER},
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return [to_role_read(role) for role in roles]
