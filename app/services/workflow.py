from uuid import uuid4

from app.config import Settings
from app.models import ContentItem, ContentStatus, Platform, SkillJob
from app.services.cards import build_review_card, build_status_card
from app.services.notifier import FeishuNotifier
from app.services.skill_runner import SkillRunner, dry_run_skill_result


class WorkflowService:
    def __init__(self, settings: Settings, notifier: FeishuNotifier | None = None, runner: SkillRunner | None = None) -> None:
        self.settings = settings
        self.notifier = notifier or FeishuNotifier(settings)
        self.runner = runner or SkillRunner(settings)

    async def create_content_from_topic(self, platform: Platform, topic: str, column: str = "") -> dict:
        content_id = f"CNT-{uuid4().hex[:12]}"
        job = SkillJob(
            content_id=content_id,
            job_id=f"JOB-{uuid4().hex[:12]}",
            platform=platform,
            topic=topic,
            column=column,
            materials=[],
        )
        skill_name = self._skill_for_platform(platform)
        try:
            result = self.runner.run(skill_name, job)
        except FileNotFoundError:
            result = dry_run_skill_result(job, skill_name)
        item = ContentItem(
            content_id=content_id,
            platform=platform,
            topic=topic,
            column=column,
            status=ContentStatus.PENDING_REVIEW,
            payload=result,
        )
        chat_id = self.settings.feishu_default_chat_id
        if chat_id:
            await self.notifier.send_card(chat_id, build_review_card([item]))
        return {"content": item.model_dump(mode="json"), "skill_result": result}

    async def approve(self, content_ids: list[str], operator_open_id: str) -> dict:
        message = f"审批通过：{', '.join(content_ids)}\n操作人：{operator_open_id or 'unknown'}"
        await self.notifier.notify_admins(message)
        return {"status": "approved", "content_ids": content_ids}

    async def status_summary(self) -> dict:
        card = build_status_card("系统状态", "服务在线。真实排期/发布统计需配置飞书多维表后读取。")
        return {"status": "ok", "card": card}

    def _skill_for_platform(self, platform: Platform) -> str:
        return {
            Platform.XHS: "content-generate-xhs",
            Platform.WECHAT: "content-generate-wechat",
            Platform.DOUYIN: "content-generate-douyin",
        }[platform]

