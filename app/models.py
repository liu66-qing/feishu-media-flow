"""Domain models for the media workflow agent."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Platform(StrEnum):
    XHS = "xhs"
    WECHAT = "wechat"
    DOUYIN = "douyin"


class TopicStatus(StrEnum):
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_topic_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DraftStatus(StrEnum):
    GENERATING = "generating"
    CRITIQUING = "critiquing"
    REVISING = "revising"
    PASSED = "passed"
    COMPOSING_IMAGE = "composing_image"
    PACKAGING = "packaging"
    AWAITING_PUBLISH_APPROVAL = "awaiting_publish_approval"
    PUBLISH_APPROVED = "publish_approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# Keep backward compat alias
class ContentStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Topic (one topic → multiple platform drafts)
# ---------------------------------------------------------------------------


class TopicBrief(BaseModel):
    topic_id: str
    topic: str
    angle: str = ""
    target_platforms: list[Platform] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    source_materials: list[str] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.PROPOSED
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    approved_at: datetime | None = None
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# Platform Draft (child of Topic)
# ---------------------------------------------------------------------------


class CriticScore(BaseModel):
    hook: int = Field(ge=1, le=5)
    information_density: int = Field(ge=1, le=5)
    naturalness: int = Field(ge=1, le=5)
    platform_fit: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)

    @property
    def total(self) -> int:
        return self.hook + self.information_density + self.naturalness + self.platform_fit + self.actionability

    @property
    def min_score(self) -> int:
        return min(self.hook, self.information_density, self.naturalness, self.platform_fit, self.actionability)


class CriticFeedback(BaseModel):
    decision: str  # "pass" | "revise" | "reject"
    scores: CriticScore
    blocking_issues: list[dict[str, str]] = Field(default_factory=list)
    keep: list[str] = Field(default_factory=list)
    change: list[str] = Field(default_factory=list)
    revision_prompt: str = ""


class PlatformDraft(BaseModel):
    draft_id: str
    topic_id: str
    platform: Platform
    version: int = 1
    status: DraftStatus = DraftStatus.GENERATING
    content: dict[str, Any] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list)
    critic_history: list[CriticFeedback] = Field(default_factory=list)
    revision_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    published_at: datetime | None = None


# ---------------------------------------------------------------------------
# Skill system (unchanged interface for郝's skills)
# ---------------------------------------------------------------------------


class SkillJob(BaseModel):
    model_config = {"extra": "allow"}

    content_id: str
    job_id: str
    platform: Platform = Platform.XHS
    topic: str = ""
    column: str = ""
    materials: list[dict[str, Any]] = Field(default_factory=list)
    brand: dict[str, Any] = Field(default_factory=dict)
    template_name: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    output_size: dict[str, Any] = Field(default_factory=lambda: {"width": 1080, "height": 1350})


class SkillResult(BaseModel):
    status: str
    timestamp: datetime
    content_id: str
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Legacy compat
# ---------------------------------------------------------------------------


class ContentItem(BaseModel):
    content_id: str
    platform: Platform
    topic: str
    column: str = ""
    status: ContentStatus = ContentStatus.DRAFT
    scheduled_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalAction(BaseModel):
    action: str
    content_ids: list[str] = Field(default_factory=list)
    operator_open_id: str = ""
