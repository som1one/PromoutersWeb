from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.branches import BranchCreate, BranchDeleteResponse, BranchRead, BranchUpdate
from promouters.services.access import is_branch_manager, is_owner, require_branch_assignment, require_owner
from promouters.services.branches import (
    create_branch,
    delete_branch,
    get_branch_or_404,
    list_branches,
    to_branch_read,
    update_branch,
)

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("", response_model=list[BranchRead])
def get_branches(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BranchRead]:
    if is_owner(current_user):
        branches = list_branches(db)
    elif is_branch_manager(current_user):
        branches = list_branches(db, branch_id=require_branch_assignment(current_user))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return [to_branch_read(branch) for branch in branches[skip : skip + limit]]


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
def create_branch_endpoint(
    payload: BranchCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchRead:
    require_owner(current_user)
    return to_branch_read(create_branch(db, payload, actor_user=current_user, request=request))


@router.get("/{branch_id}", response_model=BranchRead)
def get_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchRead:
    branch = get_branch_or_404(db, branch_id)
    if is_owner(current_user):
        return to_branch_read(branch)
    if is_branch_manager(current_user) and branch.id == require_branch_assignment(current_user):
        return to_branch_read(branch)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch_endpoint(
    branch_id: UUID,
    payload: BranchUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchRead:
    require_owner(current_user)
    branch = get_branch_or_404(db, branch_id)
    return to_branch_read(update_branch(db, branch, payload, actor_user=current_user, request=request))


@router.delete("/{branch_id}", response_model=BranchDeleteResponse)
def delete_branch_endpoint(
    branch_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchDeleteResponse:
    require_owner(current_user)
    branch = get_branch_or_404(db, branch_id)
    delete_branch(db, branch, actor_user=current_user, request=request)
    return BranchDeleteResponse(id=branch_id, message="Branch deleted")
