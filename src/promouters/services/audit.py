from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from promouters.models.operations import AuditLog
from promouters.models.users import User
from promouters.schemas.audit import AuditLogRead


def get_request_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def get_request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.headers.get("user-agent")


def write_audit_log(
    db: Session,
    *,
    actor_user: User | None,
    branch_id: UUID | None,
    entity_type: str,
    entity_id: str | None,
    action: str,
    payload: dict | None = None,
    request: Request | None = None,
    commit: bool = False,
) -> AuditLog:
    audit_log = AuditLog(
        actor_user_id=actor_user.id if actor_user is not None else None,
        branch_id=branch_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        ip_address=get_request_ip(request),
        user_agent=get_request_user_agent(request),
        payload=payload,
        created_at=datetime.now(UTC),
    )
    db.add(audit_log)
    if commit:
        db.commit()
        db.refresh(audit_log)
    return audit_log


def audit_log_query() -> Select[tuple[AuditLog]]:
    return select(AuditLog).options(joinedload(AuditLog.actor), joinedload(AuditLog.branch))


def to_audit_log_read(audit_log: AuditLog) -> AuditLogRead:
    return AuditLogRead(
        id=audit_log.id,
        actor_user_id=audit_log.actor_user_id,
        actor_username=audit_log.actor.username if audit_log.actor else None,
        branch_id=audit_log.branch_id,
        branch_name=audit_log.branch.name if audit_log.branch else None,
        entity_type=audit_log.entity_type,
        entity_id=audit_log.entity_id,
        action=audit_log.action,
        ip_address=audit_log.ip_address,
        user_agent=audit_log.user_agent,
        payload=audit_log.payload,
        created_at=audit_log.created_at,
    )


def list_audit_logs(
    db: Session,
    *,
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    branch_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[AuditLog]:
    stmt = audit_log_query()

    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if branch_id is not None:
        stmt = stmt.where(AuditLog.branch_id == branch_id)
    if created_from is not None:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditLog.created_at <= created_to)

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt))
