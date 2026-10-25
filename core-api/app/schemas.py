from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")


class PublicationStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgeStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REVOKED = "revoked"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    limit: int
    offset: int


class HospitalPublic(BaseModel):
    id: str
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    contact_phone: str
    contact_email: str
    operating_hours: str
    source: str
    verified_at: datetime | None
    is_synthetic: bool
    directions_url: str | None = None


class HospitalAdmin(HospitalPublic):
    status: PublicationStatus
    created_at: datetime
    updated_at: datetime


class HospitalCreate(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    contact_phone: str = Field(default="", max_length=50)
    contact_email: str = Field(default="", max_length=200)
    operating_hours: str = Field(default="", max_length=500)
    source: str = Field(default="", max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool = False


class HospitalUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=200)
    operating_hours: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool | None = None


class ServicePublic(BaseModel):
    id: str
    hospital_id: str
    name: str
    description: str
    requirements: str
    source: str
    verified_at: datetime | None
    is_synthetic: bool


class ServiceAdmin(ServicePublic):
    status: PublicationStatus
    created_at: datetime
    updated_at: datetime


class ServiceCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    requirements: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool = False


class ServiceUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    requirements: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool | None = None


class VisitRequirementPublic(BaseModel):
    id: str
    hospital_id: str
    title: str
    description: str
    sort_order: int
    source: str
    verified_at: datetime | None
    is_synthetic: bool


class VisitRequirementAdmin(VisitRequirementPublic):
    status: PublicationStatus
    created_at: datetime
    updated_at: datetime


class VisitRequirementCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=1000)
    source: str = Field(default="", max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool = False


class VisitRequirementUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    source: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None
    is_synthetic: bool | None = None


class ArticlePublic(BaseModel):
    id: str
    title: str
    summary: str
    content: str
    source: str
    reference_url: str
    published_at: datetime | None
    is_synthetic: bool


class ArticleAdmin(ArticlePublic):
    status: PublicationStatus
    created_at: datetime
    updated_at: datetime


class ArticleCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=20000)
    source: str = Field(default="", max_length=500)
    reference_url: str = Field(default="", max_length=500)
    is_synthetic: bool = False


class ArticleUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=20000)
    source: str | None = Field(default=None, max_length=500)
    reference_url: str | None = Field(default=None, max_length=500)
    is_synthetic: bool | None = None


class KnowledgeDocumentCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=200)
    hospital_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    content: str = Field(min_length=1, max_length=100000)
    effective_from: datetime | None = None
    review_due_at: datetime | None = None
    previous_version_id: str | None = None
    is_synthetic: bool = False
    submit_for_review: bool = False


class KnowledgeReviewRequest(StrictModel):
    decision: ReviewDecision
    reason: str = Field(default="", max_length=1000)


class StatusChangeRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=1000)


class AuditEvent(BaseModel):
    id: str
    occurred_at: datetime
    actor: str
    actor_role: str
    action: str
    object_type: str
    object_id: str
    version: str
    outcome: str
    detail: str


class KnowledgeDocumentAdmin(BaseModel):
    id: str
    document_id: str
    title: str
    source: str
    owner: str
    hospital_id: str | None = None
    version: int
    status: KnowledgeStatus
    content: str
    effective_from: datetime | None
    review_due_at: datetime | None
    previous_version_id: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_reason: str
    published_at: datetime | None
    is_synthetic: bool
    is_expired: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class ChatSafetyState(str, Enum):
    GROUNDED = "grounded"
    ABSTAINED = "abstained"
    CRISIS = "crisis"
    MEDICAL_GUARDRAIL = "medical_guardrail"
    INJECTION_BLOCKED = "injection_blocked"
    WAYFINDING_GUARDRAIL = "wayfinding_guardrail"
    FALLBACK = "fallback"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class ChatHistoryMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(StrictModel):
    session_id: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$"
    )
    hospital_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    message: str = Field(min_length=1, max_length=4000)
    consent_ai_processing: bool
    consent_version: str = Field(min_length=1, max_length=100)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=20)
    stream: bool = False


class ChatSource(BaseModel):
    source_id: str
    document_id: str
    title: str
    version: int
    published_at: datetime | None
    url: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    answer: str
    safety_state: ChatSafetyState
    sources: list[ChatSource]
    disclaimer: str
