from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.audit import AuditLogRead
from promouters.services.access import is_owner, require_branch_assignment, require_route_manager
from promouters.services.audit import list_audit_logs, to_audit_log_read

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
def get_audit_logs(
    actor_user_id: UUID | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogRead]:
    if not is_owner(current_user):
        require_route_manager(current_user)
        current_branch_id = require_branch_assignment(current_user)
        if branch_id is not None and branch_id != current_branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-branch audit access is forbidden",
            )
        branch_id = current_branch_id
    audit_logs = list_audit_logs(
        db,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        branch_id=branch_id,
        created_from=created_from,
        created_to=created_to,
        skip=skip,
        limit=limit,
    )
    return [to_audit_log_read(audit_log) for audit_log in audit_logs]
