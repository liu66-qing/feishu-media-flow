from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class Platform(StrEnum):
    XHS = "xhs"
    WECHAT = "wechat"
    DOUYIN = "douyin"


class ContentItem(BaseModel):
    content_id: str
    platform: Platform
    topic: str
    column: str = ""
    status: ContentStatus = ContentStatus.DRAFT
    scheduled_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SkillJob(BaseModel):
    content_id: str
    job_id: str
    platform: Platform
    topic: str
    column: str = ""
    materials: list[dict[str, Any]] = Field(default_factory=list)


class SkillResult(BaseModel):
    status: str
    timestamp: datetime
    content_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class ApprovalAction(BaseModel):
    action: str
    content_ids: list[str] = Field(default_factory=list)
    operator_open_id: str = ""

