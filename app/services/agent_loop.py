"""Agent loop — orchestrates content lifecycle via per-item state machine.

Triggered by:
1. External cron → POST /agent/tick (morning planning + advance due items)
2. Feishu card callback → advance specific content item

Each content item has its own state machine. The tick discovers work;
callbacks advance individual items.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models import (
    DraftStatus,
    Platform,
    PlatformDraft,
    SkillJob,
    TopicBrief,
    TopicStatus,
)
from app.services.bitable import BitableClient
from app.services.cards import (
    build_publish_review_card,
    build_schedule_card,
    build_status_card,
    build_wechat_article_card,
)
from app.services.critic import Critic
from app.services.llm import call_llm
from app.services.media_delivery import MediaDeliveryService
from app.services.notifier import FeishuNotifier
from app.services.planner import Planner
from app.services.publisher import Publisher, PublishPayload
from app.services.skill_runner import SkillRunner, dry_run_skill_result

logger = logging.getLogger(__name__)

# UTC+8 timezone
_CST = timezone(timedelta(hours=8))

# Mock topics used when hot-topic-collector skill is not available
_MOCK_WEEKLY_TOPICS = [
    {"title": "大学生社团招新季：如何打造爆款招新推文", "source": "xhs", "angle_suggestion": "从视觉设计+文案结构拆解招新推文的高赞套路", "suggested_platform": "xhs"},
    {"title": "校园新媒体运营复盘：从0到5000粉的完整路径", "source": "weibo", "angle_suggestion": "以真实数据复盘切入，拆解内容选题和发布节奏", "suggested_platform": "xhs"},
    {"title": "社团活动短视频拍摄：3个模板让你快速出片", "source": "douyin", "angle_suggestion": "提供可直接套用的分镜模板，降低拍摄门槛", "suggested_platform": "douyin"},
    {"title": "开学季校园摊位互动玩法大全", "source": "weibo", "angle_suggestion": "汇总创意互动游戏，配合实操案例", "suggested_platform": "xhs"},
    {"title": "学生组织如何做高效的复盘总结", "source": "xhs", "angle_suggestion": "给出复盘模板和流程，强调可落地", "suggested_platform": "wechat"},
]

# How long before an unapproved topic expires
TOPIC_EXPIRY_HOURS = 72
# Monthly target per platform
MONTHLY_TARGET = 4


class AgentLoop:
    """Main orchestration loop for the media workflow agent."""

    def __init__(
        self,
        settings: Settings,
        *,
        bitable: BitableClient | None = None,
        notifier: FeishuNotifier | None = None,
        planner: Planner | None = None,
        critic: Critic | None = None,
        runner: SkillRunner | None = None,
        publisher: Publisher | None = None,
        media_delivery: MediaDeliveryService | None = None,
    ) -> None:
        self.settings = settings
        self.bitable = bitable or BitableClient(settings)
        self.notifier = notifier or FeishuNotifier(settings)
        self.planner = planner or Planner()
        self.critic = critic or Critic()
        self.runner = runner or SkillRunner(settings)
        self.publisher = publisher or Publisher(settings)
        self.media_delivery = media_delivery or MediaDeliveryService(
            settings,
            notifier=self.notifier,
            runner=self.runner,
        )

    async def create_content_from_topic(
        self,
        platform: Platform,
        topic: str,
        *,
        chat_id: str = "",
        materials: list[dict] | None = None,
    ) -> dict:
        """Create one user-requested draft and run it to the approval checkpoint."""
        content_id = f"CNT-{uuid4().hex[:12]}"
        await self.bitable.create_record(
            "content",
            {
                "content_id": content_id,
                "topic": topic,
                "platform": platform.value,
                "status": DraftStatus.GENERATING.value,
                "version": 1,
                "revision_count": 0,
                "materials": _safe_json_str(materials or []),
                "chat_id": chat_id,
                "created_at": _datetime_to_feishu_ms(datetime.now(timezone.utc)),
            },
        )
        result = await self.run_until_checkpoint(content_id)
        return {"status": "created", "content_id": content_id, "result": result}

    async def run_until_checkpoint(self, item_id: str, max_steps: int = 12) -> dict:
        """Advance autonomous states until human input, a future schedule, or a terminal state."""
        autonomous = {
            TopicStatus.APPROVED.value,
            DraftStatus.GENERATING.value,
            DraftStatus.CRITIQUING.value,
            DraftStatus.PASSED.value,
            DraftStatus.COMPOSING_IMAGE.value,
            DraftStatus.PACKAGING.value,
            DraftStatus.PUBLISH_APPROVED.value,
        }
        last_result: dict = {"status": "not_found", "id": item_id}
        for _ in range(max_steps):
            record = await self._load_item(item_id)
            if not record:
                return last_result
            fields = record.get("fields", {})
            status = fields.get("status", "")
            if status == DraftStatus.SCHEDULED.value:
                if not _scheduled_at_is_due(fields.get("scheduled_at")):
                    return {"status": "waiting", "current_state": status}
            elif status not in autonomous:
                return {"status": "waiting", "current_state": status}
            last_result = await self.advance_item(item_id, reason="auto")
        return {"status": "step_limit", "id": item_id, "last_result": last_result}

    async def approve_topic(self, topic_id: str, operator_open_id: str = "") -> dict:
        return await self._approve_checkpoint(
            topic_id,
            TopicStatus.AWAITING_APPROVAL.value,
            TopicStatus.APPROVED.value,
            operator_open_id,
        )

    async def approve_publish(self, content_id: str, operator_open_id: str = "") -> dict:
        return await self._approve_checkpoint(
            content_id,
            DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
            DraftStatus.PUBLISH_APPROVED.value,
            operator_open_id,
        )

    async def reject_item(self, item_id: str, expected_status: str, operator_open_id: str = "") -> dict:
        record = await self._load_item(item_id)
        if not record:
            return {"status": "not_found", "id": item_id}
        current = record.get("fields", {}).get("status", "")
        if current != expected_status:
            return {"status": "invalid_state", "id": item_id, "current_state": current}
        await self._update_item_status(
            record,
            DraftStatus.REJECTED.value,
            {
                "reviewed_by": operator_open_id or "unknown",
                "reviewed_at": _datetime_to_feishu_ms(datetime.now(timezone.utc)),
            },
        )
        return {"status": "rejected", "id": item_id}

    async def handle_card_action(self, action_value: dict, operator_open_id: str = "") -> dict:
        """Own all AgentLoop card actions so the Feishu adapter stays transport-only."""
        action = str(action_value.get("action", ""))
        if action == "approve_topic":
            topic_id = str(action_value.get("topic_id", ""))
            result = await self.approve_topic(topic_id, operator_open_id)
            self._start_after_approval(topic_id, result)
            return result
        if action == "reject_topic":
            return await self.reject_item(
                str(action_value.get("topic_id", "")),
                TopicStatus.AWAITING_APPROVAL.value,
                operator_open_id,
            )
        if action == "approve_publish":
            content_id = str(action_value.get("content_id", ""))
            result = await self.approve_publish(content_id, operator_open_id)
            self._start_after_approval(content_id, result)
            return result
        if action == "reject_publish":
            return await self.reject_item(
                str(action_value.get("content_id", "")),
                DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
                operator_open_id,
            )
        if action == "retry_publish":
            content_id = str(action_value.get("content_id", ""))
            record = await self._load_item(content_id)
            if not record:
                return {"status": "not_found", "id": content_id}
            current = record.get("fields", {}).get("status", "")
            if current != DraftStatus.FAILED.value:
                return {"status": "invalid_state", "id": content_id, "current_state": current}
            await self._update_item_status(
                record,
                DraftStatus.SCHEDULED.value,
                {"scheduled_at": _datetime_to_feishu_ms(datetime.now(timezone.utc))},
            )
            asyncio.create_task(self.run_until_checkpoint(content_id))
            return {"status": "accepted", "id": content_id, "action": action}
        if action == "manual_takeover":
            content_id = str(action_value.get("content_id", ""))
            record = await self._load_item(content_id)
            if not record:
                return {"status": "not_found", "id": content_id}
            await self._update_item_status(record, DraftStatus.CANCELLED.value)
            return {"status": "manual_takeover", "id": content_id}
        if action == "adopt_topic":
            topic = str(action_value.get("topic_title", "")).strip()
            try:
                platform = Platform(str(action_value.get("platform", Platform.XHS.value)))
            except ValueError:
                return {"status": "error", "detail": "unknown platform"}
            if not topic:
                return {"status": "error", "detail": "missing topic_title"}
            asyncio.create_task(self.create_content_from_topic(platform, topic))
            return {"status": "accepted", "topic": topic, "platform": platform.value}
        if action in {
            "approve_all",
            "approve_ai_image",
            "reject_all",
            "confirm_publish",
            "regenerate_image",
            "reject_regenerate",
        }:
            return {
                "status": "deprecated_action",
                "action": action,
                "detail": "该卡片来自已停用的 WorkflowService 链路，请通过 /新建 重新生成。",
            }
        return {"status": "ignored", "action": action}

    async def _approve_checkpoint(
        self,
        item_id: str,
        expected_status: str,
        approved_status: str,
        operator_open_id: str,
    ) -> dict:
        if not item_id:
            return {"status": "error", "detail": "missing item id"}
        record = await self._load_item(item_id)
        if not record:
            return {"status": "not_found", "id": item_id}
        current = record.get("fields", {}).get("status", "")
        if current != expected_status:
            return {"status": "invalid_state", "id": item_id, "current_state": current}
        await self._update_item_status(
            record,
            approved_status,
            {
                "reviewed_by": operator_open_id or "unknown",
                "reviewed_at": _datetime_to_feishu_ms(datetime.now(timezone.utc)),
            },
        )
        return {"status": "accepted", "id": item_id, "next_state": approved_status}

    def _start_after_approval(self, item_id: str, result: dict) -> None:
        if result.get("status") == "accepted":
            asyncio.create_task(self.run_until_checkpoint(item_id))

    # ------------------------------------------------------------------
    # Global tick (called by cron or /agent/tick endpoint)
    # ------------------------------------------------------------------

    async def tick(self) -> dict:
        """Main tick: plan if needed, advance due items, expire stale, weekly material."""
        results = {
            "planned": await self._run_planner_if_needed(),
            "advanced": await self.advance_due_items(),
            "expired": await self._expire_stale(),
            "weekly_material": await self._check_weekly_material_card(),
        }
        logger.info("Agent tick complete: %s", results)
        return results

    # ------------------------------------------------------------------
    # Per-item state advancement (called by tick or callback)
    # ------------------------------------------------------------------

    async def advance_item(self, item_id: str, reason: str = "tick") -> dict:
        """Advance a single content item through its state machine."""
        record = await self._load_item(item_id)
        if not record:
            return {"status": "not_found", "id": item_id}

        status = record.get("fields", {}).get("status", "")
        logger.info("Advancing %s from %s (reason: %s)", item_id, status, reason)

        handlers = {
            TopicStatus.APPROVED.value: self._handle_topic_approved,
            DraftStatus.GENERATING.value: self._handle_generating,
            DraftStatus.CRITIQUING.value: self._handle_critiquing,
            DraftStatus.PASSED.value: self._handle_passed,
            DraftStatus.COMPOSING_IMAGE.value: self._handle_composing_image,
            DraftStatus.PACKAGING.value: self._handle_packaging,
            DraftStatus.PUBLISH_APPROVED.value: self._handle_publish_approved,
            DraftStatus.SCHEDULED.value: self._handle_scheduled,
        }

        handler = handlers.get(status)
        if handler:
            return await handler(record)
        return {"status": "no_action", "current_state": status}

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def _run_planner_if_needed(self) -> int:
        """Check schedule gaps and propose topics if needed."""
        gap = await self._calculate_schedule_gap()
        if gap <= 0:
            return 0

        recent = await self._get_recent_topics()
        topics = await self.planner.propose_topics(gap, recent_topics=recent)

        for topic in topics:
            await self._save_topic(topic)
            await self._send_topic_approval_card(topic)

        return len(topics)

    async def _calculate_schedule_gap(self) -> int:
        """How many more pieces of content do we need this month?"""
        try:
            records = await self.bitable.list_records("content")
            this_month = datetime.now(timezone.utc).month
            scheduled_count = sum(
                1 for r in records
                if r.get("fields", {}).get("status") in (
                    DraftStatus.SCHEDULED.value,
                    DraftStatus.PUBLISHED.value,
                    DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
                    DraftStatus.PASSED.value,
                )
            )
            total_target = MONTHLY_TARGET * len(Platform)  # 4 per platform
            return max(0, total_target - scheduled_count)
        except Exception:
            return MONTHLY_TARGET  # default: assume we need content

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    async def _handle_topic_approved(self, record: dict) -> dict:
        """Topic approved → generate drafts for each target platform."""
        fields = record.get("fields", {})
        topic = fields.get("topic", "")
        platforms_raw = fields.get("target_platforms", "xhs")
        platforms = []
        for raw_platform in str(platforms_raw).split(","):
            try:
                platforms.append(Platform(raw_platform.strip()))
            except ValueError:
                continue
        if not platforms:
            platforms = [Platform.XHS]

        drafts_created = []
        for platform in platforms:
            draft_id = f"DRAFT-{uuid4().hex[:10]}"
            await self.bitable.create_record("content", {
                "content_id": draft_id,
                "topic_id": record.get("record_id", ""),
                "topic": topic,
                "platform": platform.value,
                "status": DraftStatus.GENERATING.value,
                "version": 1,
                "revision_count": 0,
                "chat_id": fields.get("chat_id", ""),
                "created_at": _datetime_to_feishu_ms(datetime.now(timezone.utc)),
            })
            drafts_created.append(draft_id)
            await self.run_until_checkpoint(draft_id)

        await self._update_item_status(record, TopicStatus.DISPATCHED.value)
        return {"action": "generated_drafts", "drafts": drafts_created}

    async def _handle_generating(self, record: dict) -> dict:
        """Generate content using skill runner."""
        fields = record.get("fields", {})
        platform = Platform(fields.get("platform", "xhs"))
        topic = fields.get("topic", "")
        await self._generate_draft(fields.get("content_id", ""), platform, topic, fields)
        return {"action": "generation_triggered"}

    async def _handle_critiquing(self, record: dict) -> dict:
        """Run critic evaluation."""
        fields = record.get("fields", {})
        draft = PlatformDraft(
            draft_id=record.get("record_id", ""),
            topic_id=fields.get("topic_id", ""),
            platform=Platform(fields.get("platform", "xhs")),
            version=int(fields.get("version", 1)),
            status=DraftStatus.CRITIQUING,
            content=_parse_json_field(fields.get("content_payload", "{}")),
            revision_count=int(fields.get("revision_count", 0)),
        )
        if not draft.content.get("title") and draft.content.get("selected_title"):
            draft.content["title"] = draft.content["selected_title"]
        if not draft.content.get("body") and draft.content.get("body_md"):
            draft.content["body"] = draft.content["body_md"]

        feedback = await self.critic.evaluate(draft)

        if feedback.decision == "pass":
            await self._update_item_status(record, DraftStatus.PASSED.value)
        elif feedback.decision == "revise" and draft.revision_count < 3:
            await self._update_item_status(record, DraftStatus.REVISING.value, {
                "revision_count": draft.revision_count + 1,
                "critic_feedback": feedback.revision_prompt,
            })
            # Auto-trigger revision
            await self._revise_draft(record, feedback)
        else:
            await self._update_item_status(record, DraftStatus.REJECTED.value)
            await self.notifier.notify_admins(
                f"**内容被Critic拒绝**\n选题：{fields.get('topic', '')}\n原因：{feedback.revision_prompt}"
            )

        return {"action": "critiqued", "decision": feedback.decision, "score": feedback.scores.total}

    async def _handle_passed(self, record: dict) -> dict:
        """Compose and deliver platform-specific media after content review passes."""
        fields = record.get("fields", {})
        platform = fields.get("platform", "xhs")

        if platform == Platform.XHS.value:
            await self._update_item_status(record, DraftStatus.COMPOSING_IMAGE.value)
            await self._compose_image(record)
            return {"action": "composing_image"}
        if platform == Platform.DOUYIN.value:
            return await self._deliver_douyin_cards(record)
        if platform == Platform.WECHAT.value:
            return await self._deliver_wechat_article(record)
        await self._update_item_status(record, DraftStatus.AWAITING_PUBLISH_APPROVAL.value)
        await self._send_publish_approval_card(record, None)
        return {"action": "awaiting_publish_approval"}

    async def _deliver_douyin_cards(self, record: dict) -> dict:
        """Generate ordered image cards and stop at manual Douyin upload."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        content_id = fields.get("content_id", "")
        result = await self.media_delivery.compose_douyin_cards(
            content_id,
            content,
            chat_id=fields.get("chat_id", ""),
            use_ai_image=True,
        )
        if not result:
            await self._update_item_status(record, DraftStatus.FAILED.value)
            return {"action": "douyin_card_delivery_failed"}
        await self._update_item_status(
            record,
            DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
            {"image_result": _safe_json_str(result)},
        )
        return {"action": "douyin_cards_delivered", "card_count": len(result.get("card_paths", []))}

    async def _deliver_wechat_article(self, record: dict) -> dict:
        """Send the article, create labeled images, and attempt a WeChat draft."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        content_id = fields.get("content_id", "")
        chat_id = fields.get("chat_id") or self.settings.feishu_default_chat_id
        title = content.get("selected_title") or content.get("title") or fields.get("topic", "")
        if chat_id:
            await self.notifier.send_card(
                chat_id,
                build_wechat_article_card(
                    title=title,
                    summary=str(content.get("summary", "")),
                    body_md=str(content.get("body_md") or content.get("body") or ""),
                    hashtags=[str(tag) for tag in content.get("hashtags", [])],
                    content_id=content_id,
                ),
            )

        result = await self.media_delivery.compose_wechat_package(
            content_id,
            content,
            chat_id=chat_id,
            use_ai_image=True,
        )
        await self._update_item_status(
            record,
            DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
            {"image_result": _safe_json_str(result)},
        )
        return {
            "action": "wechat_article_delivered",
            "draft_created": bool(result.get("draft_created")),
            "image_count": len(result.get("assets", [])),
        }

    async def _handle_composing_image(self, record: dict) -> dict:
        """Run image-compose skill for XHS cover/cards."""
        fields = record.get("fields", {})
        await self._compose_image(record)
        return {"action": "image_composed"}

    async def _handle_packaging(self, record: dict) -> dict:
        """Run xhs-publish-package to assemble final publish bundle."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        image_result = _parse_json_field(fields.get("image_result", "{}"))
        image_paths = _image_paths(image_result)

        job = SkillJob(
            content_id=fields.get("content_id", ""),
            job_id=f"JOB-{uuid4().hex[:8]}",
            title=content.get("title", content.get("selected_title", "")),
            body=content.get("body", ""),
            hashtags=content.get("hashtags", []),
            cover_image=image_result.get("cover_path", image_result.get("image_path", "")),
            card_images=image_result.get("card_paths", []),
            assets=[{"type": "image", "path": path} for path in image_paths],
        )

        try:
            result = await asyncio.to_thread(self.runner.run, "xhs-publish-package", job)
            package_result = _result_data(result)
            package_result["asset_paths"] = _package_asset_paths(package_result)
            await self.bitable.update_record("content", record["record_id"], {
                "status": DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
                "package_result": _safe_json_str(package_result),
            })
            await self._send_publish_approval_card(record, None)
        except Exception as e:
            logger.error("Packaging failed for %s: %s", record.get("record_id"), e)
            await self._update_item_status(record, DraftStatus.FAILED.value)

        return {"action": "packaged"}

    async def _handle_publish_approved(self, record: dict) -> dict:
        """Admin approved publish → make it immediately eligible for upload."""
        await self._update_item_status(
            record,
            DraftStatus.SCHEDULED.value,
            {"scheduled_at": _datetime_to_feishu_ms(datetime.now(timezone.utc))},
        )
        return {"action": "scheduled"}

    async def _handle_scheduled(self, record: dict) -> dict:
        """Scheduled content → auto-publish via social-auto-upload."""
        fields = record.get("fields", {})
        platform = fields.get("platform", "xhs")
        if platform in {Platform.DOUYIN.value, Platform.WECHAT.value}:
            await self._update_item_status(record, DraftStatus.AWAITING_PUBLISH_APPROVAL.value)
            return {"action": "manual_delivery_only", "platform": platform}
        content = _parse_json_field(fields.get("content_payload", "{}"))
        package = _parse_json_field(fields.get("package_result", "{}"))
        image_result = _parse_json_field(fields.get("image_result", "{}"))

        # Determine account name from accounts table or default
        account = await self._get_account_for_platform(platform)
        if not account:
            logger.error("No account configured for platform %s", platform)
            await self._notify_publish_failure(record, "No account configured")
            return {"action": "publish_failed", "reason": "no_account"}

        # Build image paths from package or image result
        image_paths = package.get("asset_paths", [])
        if not image_paths:
            cover = image_result.get("cover_path", "")
            cards = image_result.get("card_paths", [])
            image_paths = ([cover] if cover else []) + cards

        payload = PublishPayload(
            platform=platform,
            account=account,
            title=content.get("title", content.get("selected_title", "")),
            body=content.get("body", ""),
            tags=content.get("hashtags", []),
            image_paths=image_paths,
        )

        await self._update_item_status(record, DraftStatus.PUBLISHING.value)
        result = await asyncio.to_thread(self.publisher.publish, payload)

        if result.success:
            await self._update_item_status(record, DraftStatus.PUBLISHED.value)
            await self.notifier.notify_admins(
                f"✅ 发布成功\n平台：{platform}\n标题：{payload.title}"
            )
            return {"action": "published"}
        else:
            await self._update_item_status(record, DraftStatus.FAILED.value)
            await self._notify_publish_failure(record, result.message)
            return {"action": "publish_failed", "reason": result.message}

    async def _get_account_for_platform(self, platform: str) -> str | None:
        """Look up configured account name from accounts table."""
        try:
            records = await self.bitable.list_records("accounts")
            for r in records:
                f = r.get("fields", {})
                if f.get("platform") == platform and f.get("status") == "active":
                    return f.get("account_name", "")
        except Exception:
            pass
        return self.settings.social_auto_upload_default_account or None

    async def _notify_publish_failure(self, record: dict, error: str) -> None:
        """Send failure notification to admins via Feishu with retry option."""
        fields = record.get("fields", {})
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "red", "title": {"tag": "plain_text", "content": "❌ 发布失败"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**平台**：{fields.get('platform', '')}\n"
                    f"**标题**：{fields.get('topic', '')}\n"
                    f"**错误**：{error[:300]}"
                )}},
                {"tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "重试发布"}, "type": "primary",
                     "value": {"action": "retry_publish", "content_id": fields.get("content_id", "")}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "人工接管"}, "type": "default",
                     "value": {"action": "manual_takeover", "content_id": fields.get("content_id", "")}},
                ]},
            ],
        }
        chat_id = self.settings.feishu_default_chat_id
        if chat_id:
            await self.notifier.send_card(chat_id, card)

    # ------------------------------------------------------------------
    # Generation & Revision
    # ------------------------------------------------------------------

    async def _generate_draft(self, draft_id: str, platform: Platform, topic: str, fields: dict) -> None:
        """Call the appropriate generation skill."""
        from app.services.skill_runner import dry_run_skill_result

        job = SkillJob(
            content_id=draft_id,
            job_id=f"JOB-{uuid4().hex[:8]}",
            platform=platform,
            topic=topic,
            materials=_parse_list_field(fields.get("materials", "[]")),
        )

        skill_name = {
            Platform.XHS: "content-generate-xhs",
            Platform.WECHAT: "content-generate-wechat",
            Platform.DOUYIN: "content-generate-douyin",
        }[platform]

        try:
            result = await asyncio.to_thread(self.runner.run, skill_name, job)
        except FileNotFoundError:
            result = dry_run_skill_result(job, skill_name)
        content = _result_data(result)

        # Save generated content and move to critiquing
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == draft_id:
                    await self.bitable.update_record("content", r["record_id"], {
                        "status": DraftStatus.CRITIQUING.value,
                        "content_payload": _safe_json_str(content),
                    })
                    break
        except Exception as e:
            logger.error("Failed to save draft %s: %s", draft_id, e)

    async def _revise_draft(self, record: dict, feedback) -> None:
        """Ask executor to revise based on critic feedback."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        platform = fields.get("platform", "xhs")

        revision_system = (
            "你是内容修改专家。根据Critic的反馈修改以下内容。\n"
            "只修改Critic指出的问题，保留Critic认可的部分。\n"
            "输出完整的修改后JSON（同原格式）。"
        )
        revision_user = (
            f"## 目标平台\n{platform}\n\n"
            f"## 原始内容\n```json\n{_safe_json_str(content)}\n```\n\n"
            f"## Critic反馈\n{feedback.revision_prompt}\n\n"
            f"## 需要保留的\n{', '.join(feedback.keep) if feedback.keep else '无特别指出'}\n\n"
            f"## 需要修改的\n{', '.join(feedback.change) if feedback.change else '见反馈'}\n\n"
            "请输出修改后的完整内容JSON。"
        )

        raw = await call_llm(revision_system, revision_user, response_json=True)
        try:
            revised = _parse_json_field(raw)
            # Save and re-enter critiquing
            await self.bitable.update_record("content", record["record_id"], {
                "status": DraftStatus.CRITIQUING.value,
                "content_payload": _safe_json_str(revised),
                "version": int(fields.get("version", 1)) + 1,
            })
        except Exception as e:
            logger.error("Revision failed for %s: %s", record.get("record_id"), e)

    async def _compose_image(self, record: dict) -> None:
        """Call image-compose skill, then advance to packaging."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        title = str(content.get("title") or content.get("selected_title") or "")

        job = SkillJob(
            content_id=fields.get("content_id", ""),
            job_id=f"JOB-{uuid4().hex[:8]}",
            template_name="",
            image_mode="ai_bg",
            variables={
                "title": content.get("cover_text") or title[:24] or "校园主题精选",
                "subtitle": title if content.get("cover_text") else "",
                "brand_name": "校园新媒体",
                "series_name": "本期精选",
                "section_label": "校园主题精选",
                "page_number": "01",
                "page_label": "01 / 01",
                "footer": "校园内容工作流",
                "ai_prompt": content.get("cover_text") or title,
                "visual_style": content.get("visual_style", "auto"),
                "template_role": "cover",
            },
            output_size={"width": 1080, "height": 1350},
        )

        try:
            result = await asyncio.to_thread(self.runner.run, "image-compose", job)
            image_result = _result_data(result)
            if image_result.get("image_path") and not image_result.get("cover_path"):
                image_result["cover_path"] = image_result["image_path"]
            image_result.setdefault("card_paths", [])
            await self.bitable.update_record("content", record["record_id"], {
                "status": DraftStatus.PACKAGING.value,
                "image_result": _safe_json_str(image_result),
            })
        except Exception as e:
            logger.error("Image compose failed for %s: %s", record.get("record_id"), e)
            # Fall through to packaging without images
            await self._update_item_status(record, DraftStatus.PACKAGING.value)

    # ------------------------------------------------------------------
    # Feishu cards (human checkpoints)
    # ------------------------------------------------------------------

    async def _send_topic_approval_card(self, topic: TopicBrief) -> None:
        """Send topic proposal card to admin for approval."""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "blue", "title": {"tag": "plain_text", "content": "📋 选题审批"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**选题**：{topic.topic}\n"
                    f"**角度**：{topic.angle}\n"
                    f"**平台**：{', '.join(p.value for p in topic.target_platforms)}\n"
                    f"**要点**：{'; '.join(topic.key_points[:3])}"
                )}},
                {"tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "通过"}, "type": "primary",
                     "value": {"action": "approve_topic", "topic_id": topic.topic_id}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "拒绝"}, "type": "danger",
                     "value": {"action": "reject_topic", "topic_id": topic.topic_id}},
                ]},
            ],
        }
        chat_id = self.settings.feishu_default_chat_id
        if chat_id:
            await self.notifier.send_card(chat_id, card)

    async def _send_publish_approval_card(self, record: dict, draft: PlatformDraft | None) -> None:
        """Send final content for admin publish approval."""
        fields = record.get("fields", {})
        content = _parse_json_field(fields.get("content_payload", "{}"))
        title = content.get("title") or content.get("selected_title") or fields.get("topic", "")
        image_result = _parse_json_field(fields.get("image_result", "{}"))
        image_paths = _image_paths(image_result)
        image_keys = []
        for image_path in image_paths:
            image_key = await self.notifier.upload_image(image_path)
            if image_key:
                image_keys.append(image_key)

        card = build_publish_review_card(
            content_id=fields.get("content_id", ""),
            platform=fields.get("platform", ""),
            title=title,
            body=str(content.get("body", content.get("body_md", ""))),
            hashtags=[str(tag) for tag in content.get("hashtags", [])],
            image_keys=image_keys,
        )
        chat_id = fields.get("chat_id") or self.settings.feishu_default_chat_id
        if chat_id:
            await self.notifier.send_card(chat_id, card)

    # ------------------------------------------------------------------
    # Weekly material card (Monday)
    # ------------------------------------------------------------------

    async def _check_weekly_material_card(self) -> str:
        """Send weekly hot-topic material card on Monday (UTC+8)."""
        now_cst = datetime.now(_CST)
        if now_cst.weekday() != 0:
            return "not_monday"

        date_str = now_cst.strftime("%Y-%m-%d")
        flag_path = self.settings.data_dir / f"weekly_material_sent_{date_str}.flag"
        if flag_path.exists():
            return "already_sent"

        # Collect hot topics via skill or fallback to mock
        topics = await self._collect_weekly_topics()

        from app.services.cards import build_material_review_card
        card = build_material_review_card(topics)

        chat_id = self.settings.feishu_default_chat_id
        if not chat_id:
            logger.warning("No feishu_default_chat_id, skip weekly material card")
            return "no_chat_id"

        await self.notifier.send_card(chat_id, card)

        # Write flag to prevent duplicate send
        flag_path.write_text(date_str, encoding="utf-8")
        logger.info("Weekly material card sent for %s (%d topics)", date_str, len(topics))
        return f"sent_{len(topics)}_topics"

    async def _collect_weekly_topics(self) -> list[dict]:
        """Run hot-topic-collector skill; fallback to mock data on failure."""
        job = SkillJob(
            content_id="WEEKLY",
            job_id=f"JOB-WEEKLY-{uuid4().hex[:8]}",
            topic="weekly_hot_topics",
            materials=[],
        )
        # Build input with keywords/platforms for hot-topic-collector
        job_input = {
            "keywords": ["大学生", "社团", "运营", "校园", "新媒体"],
            "platforms": ["weibo", "douyin", "xhs"],
            "max_topics": 10,
        }
        # SkillRunner writes job.model_dump_json() as input.json, but
        # hot-topic-collector expects its own fields. We write a custom input.
        try:
            result = self.runner.run("hot-topic-collector", job)
            topics = result.get("topics", [])
            if topics:
                return topics[:10]
        except (FileNotFoundError, RuntimeError) as e:
            logger.warning("hot-topic-collector unavailable, using mock: %s", e)

        return _MOCK_WEEKLY_TOPICS

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    async def advance_due_items(self) -> int:
        """Find items that need advancement and process them."""
        advanced = 0
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                fields = r.get("fields", {})
                status = fields.get("status", "")
                if status in (
                    TopicStatus.APPROVED.value,
                    DraftStatus.GENERATING.value,
                    DraftStatus.CRITIQUING.value,
                    DraftStatus.PASSED.value,
                    DraftStatus.COMPOSING_IMAGE.value,
                    DraftStatus.PACKAGING.value,
                    DraftStatus.PUBLISH_APPROVED.value,
                ) or (
                    status == DraftStatus.SCHEDULED.value
                    and _scheduled_at_is_due(fields.get("scheduled_at"))
                ):
                    item_id = fields.get("content_id") or r.get("record_id", "")
                    await self.run_until_checkpoint(item_id)
                    advanced += 1
        except Exception as e:
            logger.warning("advance_due_items error: %s", e)
        return advanced

    async def status_summary(self) -> dict:
        try:
            records = await self.bitable.list_records("content")
            counts: dict[str, int] = {}
            for record in records:
                status = record.get("fields", {}).get("status", "unknown")
                counts[status] = counts.get(status, 0) + 1
            summary = "\n".join(f"- {status}: {count}" for status, count in sorted(counts.items())) or "暂无内容"
            card = build_status_card("系统状态", summary)
        except Exception:
            card = build_status_card("系统状态", "多维表未配置，无法读取状态。")
        return {"status": "ok", "card": card}

    async def get_schedule(self) -> dict:
        try:
            records = await self.bitable.list_records("content")
            items = []
            for record in records:
                fields = record.get("fields", {})
                if fields.get("status") in {
                    DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
                    DraftStatus.PUBLISH_APPROVED.value,
                    DraftStatus.SCHEDULED.value,
                    DraftStatus.PUBLISHING.value,
                }:
                    items.append(
                        {
                            "topic": fields.get("topic", ""),
                            "platform": fields.get("platform", ""),
                            "scheduled_at": fields.get("scheduled_at", "待定"),
                            "status": fields.get("status", ""),
                        }
                    )
            card = build_schedule_card(items, self.settings.feishu_bitable_app_token)
        except Exception:
            card = build_schedule_card([])
        return {"status": "ok", "card": card}

    async def _expire_stale(self) -> int:
        """Expire topics/approvals that have been waiting too long."""
        expired = 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=TOPIC_EXPIRY_HOURS)
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                fields = r.get("fields", {})
                if fields.get("status") == TopicStatus.AWAITING_APPROVAL.value:
                    created = fields.get("created_at", "")
                    created_at = _parse_feishu_datetime(created)
                    if created_at and created_at < cutoff:
                        await self.bitable.update_record("content", r["record_id"], {"status": TopicStatus.EXPIRED.value})
                        expired += 1
        except Exception as e:
            logger.warning("expire_stale error: %s", e)
        return expired

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_recent_topics(self) -> list[str]:
        try:
            records = await self.bitable.list_records("content")
            return [r.get("fields", {}).get("topic", "") for r in records[-20:] if r.get("fields", {}).get("topic")]
        except Exception:
            return []

    async def _save_topic(self, topic: TopicBrief) -> None:
        try:
            await self.bitable.create_record("content", {
                "content_id": topic.topic_id,
                "topic": topic.topic,
                "target_platforms": ",".join(p.value for p in topic.target_platforms),
                "status": TopicStatus.AWAITING_APPROVAL.value,
                "key_points": "; ".join(topic.key_points),
                "created_at": _datetime_to_feishu_ms(topic.created_at),
            })
        except Exception as e:
            logger.error("Failed to save topic %s: %s", topic.topic_id, e)

    async def _load_item(self, item_id: str) -> dict | None:
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                if r.get("record_id") == item_id or r.get("fields", {}).get("content_id") == item_id:
                    return r
        except Exception:
            pass
        return None

    async def _update_item_status(self, record: dict, status: str, extra_fields: dict | None = None) -> None:
        fields = {"status": status}
        if extra_fields:
            fields.update(extra_fields)
        try:
            await self.bitable.update_record("content", record["record_id"], fields)
        except Exception as e:
            logger.error("Failed to update status for %s: %s", record.get("record_id"), e)
            raise


def _parse_json_field(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {"items": raw}
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return {}


def _safe_json_str(obj) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def _parse_list_field(raw) -> list:
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _result_data(result: dict) -> dict:
    nested = result.get("data")
    if isinstance(nested, dict):
        return dict(nested)
    return {
        key: value
        for key, value in result.items()
        if key not in {"status", "timestamp", "generated_at"}
    }


def _image_paths(image_result: dict) -> list[str]:
    cover = image_result.get("cover_path") or image_result.get("image_path") or ""
    cards = image_result.get("card_paths") or image_result.get("image_paths") or []
    paths = ([cover] if cover else []) + list(cards)
    return [str(path) for path in paths if path]


def _package_asset_paths(package_result: dict) -> list[str]:
    package_path = package_result.get("publish_package_path")
    if not package_path:
        return []
    assets_dir = Path(str(package_path)) / "assets"
    if not assets_dir.exists():
        return []
    return [str(path) for path in sorted(assets_dir.iterdir()) if path.is_file() and path.suffix != ".missing"]


def _scheduled_at_is_due(raw) -> bool:
    due_at = _parse_feishu_datetime(raw)
    if due_at is None:
        return False
    return due_at <= datetime.now(timezone.utc)


def _datetime_to_feishu_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _parse_feishu_datetime(raw) -> datetime | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value > 10_000_000_000:
            value /= 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
