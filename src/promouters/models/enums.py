from enum import StrEnum


class RoleCode(StrEnum):
    OWNER = "owner"
    BRANCH_MANAGER = "branch_manager"
    AD_DIRECTOR = "ad_director"
    DISPATCHER = "dispatcher"
    DIRECTOR = "director"
    MASTER = "master"
    PROMOTER = "promoter"
    USER = "user"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class RouteStatus(StrEnum):
    DRAFT = "draft"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RoutePointType(StrEnum):
    START = "start"
    CHECKPOINT = "checkpoint"
    STOP = "stop"
    FINISH = "finish"


class PromoterSessionStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GeoPingSource(StrEnum):
    START = "start"
    TRACKING = "tracking"
    FINISH = "finish"
    PHOTO = "photo"
    MANUAL = "manual"


class PhotoReportStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PayoutRateType(StrEnum):
    HOURLY = "hourly"
    PER_LEAFLET = "per_leaflet"
    FIXED_SHIFT = "fixed_shift"


class PayoutStatus(StrEnum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    PUSH = "push"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"


class ExpensePlanStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ExpenseApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class MasterRequestStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    ON_THE_WAY = "on_the_way"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    HANDED_OVER = "handed_over"
    CANCELLED = "cancelled"


# Статусы, при которых геопозиция мастера должна собираться автоматически
GEO_TRACKED_MASTER_STATUSES: frozenset[MasterRequestStatus] = frozenset(
    {MasterRequestStatus.ON_THE_WAY, MasterRequestStatus.IN_PROGRESS}
)


class PromoterReportReviewStatus(StrEnum):
    """Состояние приёма итогового отчёта промоутера директором по рекламе."""

    PENDING = "pending"
    ACCEPTED_BY_DIRECTOR = "accepted_by_director"
    FORWARDED_TO_MANAGER = "forwarded_to_manager"
    REJECTED = "rejected"


class AttachmentType(StrEnum):
    BSO = "bso"
    CONTRACT = "contract"
    PHOTO = "photo"
    OTHER = "other"
