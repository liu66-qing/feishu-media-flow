"""Agent loop — orchestrates content lifecycle via per-item state machine.

Triggered by:
1. External cron → POST /agent/tick (morning planning + advance due items)
2. Feishu card callback → advance specific content item

Each content item has its own state machine. The tick discovers work;
callbacks advance individual items.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
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
from app.services.critic import Critic
from app.services.llm import call_llm
from app.services.notifier import FeishuNotifier
from app.services.planner import Planner
from app.services.publisher import Publisher, PublishPayload
from app.services.skill_runner import SkillRunner

logger = logging.getLogger(__name__)

# How long before an unapproved topic expires
TOPIC_EXPIRY_HOURS = 72
# Monthly target per platform
MONTHLY_TARGET = 4


class AgentLoop:
    """Main orchestration loop for the media workflow agent."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bitable = BitableClient(settings)
        self.notifier = FeishuNotifier(settings)
        self.planner = Planner()
        self.critic = Critic()
        self.runner = SkillRunner(settings)
        self.publisher = Publisher(settings)

    # ------------------------------------------------------------------
    # Global tick (called by cron or /agent/tick endpoint)
    # ------------------------------------------------------------------

    async def tick(self) -> dict:
        """Main tick: plan if needed, advance due items, expire stale."""
        results = {
            "planned": await self._run_planner_if_needed(),
            "advanced": await self._advance_due_items(),
            "expired": await self._expire_stale(),
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
        platforms = [Platform(p.strip()) for p in platforms_raw.split(",") if p.strip() in Platform.__members__.values()]

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
            })
            drafts_created.append(draft_id)
            # Trigger generation immediately
            await self._generate_draft(draft_id, platform, topic, fields)

        return {"action": "generated_drafts", "drafts": drafts_created}

    async def _handle_generating(self, record: dict) -> dict:
        """Generate content using skill runner."""
        fields = record.get("fields", {})
        platform = Platform(fields.get("platform", "xhs"))
        topic = fields.get("topic", "")
        await self._generate_draft(record.get("record_id", ""), platform, topic, fields)
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

        feedback = await self.critic.evaluate(draft)

        if feedback.decision == "pass":
            await self._update_item_status(record, DraftStatus.PASSED.value)
            await self._send_publish_approval_card(record, draft)
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
        """Content passed critic → XHS goes to image compose, others to publish approval."""
        fields = record.get("fields", {})
        platform = fields.get("platform", "xhs")

        if platform == Platform.XHS.value:
            await self._update_item_status(record, DraftStatus.COMPOSING_IMAGE.value)
            await self._compose_image(record)
            return {"action": "composing_image"}
        else:
            await self._send_publish_approval_card(record, None)
            await self._update_item_status(record, DraftStatus.AWAITING_PUBLISH_APPROVAL.value)
            return {"action": "awaiting_publish_approval"}

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

        job = SkillJob(
            content_id=fields.get("content_id", ""),
            job_id=f"JOB-{uuid4().hex[:8]}",
            title=content.get("title", content.get("selected_title", "")),
            body=content.get("body", ""),
            hashtags=content.get("hashtags", []),
            cover_image=image_result.get("cover_path", ""),
            card_images=image_result.get("card_paths", []),
        )

        try:
            result = self.runner.run("xhs-publish-package", job)
            await self.bitable.update_record("content", record["record_id"], {
                "status": DraftStatus.AWAITING_PUBLISH_APPROVAL.value,
                "package_result": _safe_json_str(result.get("data", {})),
            })
            await self._send_publish_approval_card(record, None)
        except Exception as e:
            logger.error("Packaging failed for %s: %s", record.get("record_id"), e)
            await self._update_item_status(record, DraftStatus.FAILED.value)

        return {"action": "packaged"}

    async def _handle_publish_approved(self, record: dict) -> dict:
        """Admin approved publish → schedule it."""
        await self._update_item_status(record, DraftStatus.SCHEDULED.value)
        return {"action": "scheduled"}

    async def _handle_scheduled(self, record: dict) -> dict:
        """Scheduled content → auto-publish via social-auto-upload."""
        fields = record.get("fields", {})
        platform = fields.get("platform", "xhs")
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
        result = self.publisher.publish(payload)

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
        return None

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
            materials=_parse_json_field(fields.get("materials", "[]")),
        )

        skill_name = {
            Platform.XHS: "content-generate-xhs",
            Platform.WECHAT: "content-generate-wechat",
            Platform.DOUYIN: "content-generate-douyin",
        }[platform]

        try:
            result = self.runner.run(skill_name, job)
        except FileNotFoundError:
            result = dry_run_skill_result(job, skill_name)

        # Save generated content and move to critiquing
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == draft_id:
                    await self.bitable.update_record("content", r["record_id"], {
                        "status": DraftStatus.CRITIQUING.value,
                        "content_payload": _safe_json_str(result.get("data", {})),
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
        title = content.get("title", content.get("selected_title", ""))

        job = SkillJob(
            content_id=fields.get("content_id", ""),
            job_id=f"JOB-{uuid4().hex[:8]}",
            template_name="xhs-cover-01",
            variables={
                "title": title[:20] if title else "untitled",
                "subtitle": content.get("cover_text", ""),
                "bg_color": "#FF6B6B",
                "accent_color": "#FFFFFF",
            },
            output_size={"width": 1080, "height": 1350},
        )

        try:
            result = self.runner.run("image-compose", job)
            await self.bitable.update_record("content", record["record_id"], {
                "status": DraftStatus.PACKAGING.value,
                "image_result": _safe_json_str(result.get("data", {})),
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
        title = content.get("title", content.get("selected_title", fields.get("topic", "")))

        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "green", "title": {"tag": "plain_text", "content": "✅ 内容发布审批"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**标题**：{title}\n"
                    f"**平台**：{fields.get('platform', '')}\n"
                    f"**正文预览**：{str(content.get('body', ''))[:200]}..."
                )}},
                {"tag": "action", "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "发布"}, "type": "primary",
                     "value": {"action": "approve_publish", "content_id": fields.get("content_id", "")}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "打回修改"}, "type": "default",
                     "value": {"action": "reject_publish", "content_id": fields.get("content_id", "")}},
                ]},
            ],
        }
        chat_id = self.settings.feishu_default_chat_id
        if chat_id:
            await self.notifier.send_card(chat_id, card)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    async def _advance_due_items(self) -> int:
        """Find items that need advancement and process them."""
        advanced = 0
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                status = r.get("fields", {}).get("status", "")
                if status in (
                    DraftStatus.GENERATING.value,
                    DraftStatus.CRITIQUING.value,
                    DraftStatus.PASSED.value,
                    DraftStatus.COMPOSING_IMAGE.value,
                    DraftStatus.PACKAGING.value,
                ):
                    await self.advance_item(r.get("record_id", ""), reason="tick")
                    advanced += 1
        except Exception as e:
            logger.warning("advance_due_items error: %s", e)
        return advanced

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
                    if created and datetime.fromisoformat(str(created).replace("Z", "+00:00")) < cutoff:
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
                "created_at": topic.created_at.isoformat(),
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
