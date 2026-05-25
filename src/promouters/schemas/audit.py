from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_username: str | None = None
    branch_id: UUID | None
    branch_name: str | None = None
    entity_type: str
    entity_id: str | None
    action: str
    ip_address: str | None
    user_agent: str | None
    payload: dict | None
    created_at: datetime
