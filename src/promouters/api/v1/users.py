from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from promouters.api.deps import get_current_user
from promouters.db.session import get_db
from promouters.models.users import User
from promouters.schemas.users import (
    CurrentUserUpdate,
    UserCreate,
    UserDeleteResponse,
    UserRead,
    UserUpdate,
)
from promouters.services.users import (
    create_user,
    delete_user,
    get_user_for_actor,
    get_user_or_404,
    list_users_for_actor,
    to_user_read,
    update_current_user,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def get_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserRead]:
    return [to_user_read(user) for user in list_users_for_actor(db, current_user, skip=skip, limit=limit)]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return to_user_read(create_user(db, current_user, payload, request=request))


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserRead:
    return to_user_read(get_user_or_404(db, current_user.id))


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: CurrentUserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = get_user_or_404(db, current_user.id)
    return to_user_read(update_current_user(db, user, payload, request=request))


@router.delete("/me", response_model=UserDeleteResponse)
def delete_me(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDeleteResponse:
    user = get_user_or_404(db, current_user.id)
    user_id = user.id
    delete_user(db, current_user, user, request=request, action="user.self_delete")
    return UserDeleteResponse(id=user_id, message="Current user deleted")


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return to_user_read(get_user_for_actor(db, current_user, user_id))


@router.patch("/{user_id}", response_model=UserRead)
def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = get_user_for_actor(db, current_user, user_id)
    return to_user_read(update_user(db, current_user, user, payload, request=request))


@router.delete("/{user_id}", response_model=UserDeleteResponse)
def delete_user_endpoint(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDeleteResponse:
    user = get_user_for_actor(db, current_user, user_id)
    delete_user(db, current_user, user, request=request)
    return UserDeleteResponse(id=user_id, message="User deleted")
