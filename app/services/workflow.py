import logging
from uuid import uuid4

from app.config import Settings
from app.models import ContentItem, ContentStatus, Platform, SkillJob
from app.services.bitable import BitableClient
from app.services.cards import build_review_card, build_status_card
from app.services.notifier import FeishuNotifier
from app.services.skill_runner import SkillRunner, dry_run_skill_result

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(
        self,
        settings: Settings,
        notifier: FeishuNotifier | None = None,
        runner: SkillRunner | None = None,
        bitable: BitableClient | None = None,
    ) -> None:
        self.settings = settings
        self.notifier = notifier or FeishuNotifier(settings)
        self.runner = runner or SkillRunner(settings)
        self.bitable = bitable or BitableClient(settings)

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

        # Step 1: generate content (run in thread to avoid blocking event loop)
        import asyncio

        skill_name = self._skill_for_platform(platform)
        try:
            result = await asyncio.to_thread(self.runner.run, skill_name, job)
        except FileNotFoundError:
            result = dry_run_skill_result(job, skill_name)

        # Step 2: risk-check
        risk_result = await self._run_risk_check(job, result)
        risk_level = risk_result.get("data", {}).get("risk_level", "low")

        if risk_level == "high":
            status = ContentStatus.FAILED
        else:
            status = ContentStatus.PENDING_REVIEW

        item = ContentItem(
            content_id=content_id,
            platform=platform,
            topic=topic,
            column=column,
            status=status,
            payload={"generation": result, "risk_check": risk_result},
        )

        # Step 3: persist to bitable
        await self._persist_content(item)

        # Step 4: notify
        chat_id = self.settings.feishu_default_chat_id
        if chat_id and status == ContentStatus.PENDING_REVIEW:
            if platform == Platform.WECHAT:
                # Send wechat article card with collapsible full text
                from app.services.cards import build_wechat_article_card
                title = result.get("selected_title", topic)
                summary = result.get("summary", "")
                body_md = result.get("body_md", "")
                hashtags = result.get("hashtags", [])
                card = build_wechat_article_card(title, summary, body_md, hashtags)
                await self.notifier.send_card(chat_id, card)
            else:
                await self.notifier.send_card(chat_id, build_review_card([item]))
        elif status == ContentStatus.FAILED:
            await self.notifier.notify_admins(
                f"**内容被风控拦截**\n选题：{topic}\n原因：{risk_result.get('data', {}).get('reason', 'unknown')}"
            )

        return {"content": item.model_dump(mode="json"), "skill_result": result, "risk_result": risk_result}

    async def approve(self, content_ids: list[str], operator_open_id: str) -> dict:
        import asyncio

        for cid in content_ids:
            await self._update_content_status(cid, ContentStatus.APPROVED)
        message = f"审批通过：{', '.join(content_ids)}\n操作人：{operator_open_id or 'unknown'}"
        await self.notifier.notify_admins(message)

        # Trigger image compose in background for each approved content
        for cid in content_ids:
            asyncio.create_task(self._compose_image_for_content(cid))

        return {"status": "approved", "content_ids": content_ids}

    async def _compose_image_for_content(self, content_id: str) -> None:
        """Run image-compose skill after approval."""
        import asyncio
        import json

        # Find the generation output by scanning job dirs
        jobs_dir = self.settings.data_dir / "jobs"
        gen_data = None
        if jobs_dir.exists():
            for job_dir in sorted(jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                output_file = job_dir / "content-generate-xhs.json"
                if output_file.exists():
                    data = json.loads(output_file.read_text(encoding="utf-8"))
                    if data.get("content_id") == content_id:
                        gen_data = data
                        break

        if not gen_data:
            await self.notifier.notify_admins(f"⚠️ 图文合成跳过：找不到 {content_id} 的生成结果")
            return

        # Build image-compose input
        title = gen_data.get("selected_title", gen_data.get("topic", ""))
        cover_text = gen_data.get("cover_text", "")
        compose_job = SkillJob(
            content_id=content_id,
            job_id=f"JOB-IMG-{content_id[4:]}",
            platform=Platform.XHS,
            topic=title,
            column="",
            materials=[],
            template_name="xhs-cover-01",
            variables={
                "title": cover_text or title,
                "subtitle": title if cover_text else "",
                "bg_color": "#FF6B6B",
                "accent_color": "#FFFFFF",
            },
        )

        try:
            result = await asyncio.to_thread(self.runner.run, "image-compose", compose_job)
            image_path = result.get("data", {}).get("image_path", "")
            # Upload image to Feishu and send as card
            chat_id = self.settings.feishu_default_chat_id
            if image_path and chat_id:
                image_key = await self.notifier.upload_image(image_path)
                if image_key:
                    title = gen_data.get("selected_title", gen_data.get("topic", ""))
                    await self.notifier.send_image_card(chat_id, image_key, title, content_id)
                else:
                    await self.notifier.notify_admins(f"🎨 封面图生成完成但上传失败：{content_id}\n路径：{image_path}")
            else:
                await self.notifier.notify_admins(f"🎨 封面图生成完成：{content_id}\n路径：{image_path}")
            # Auto-schedule: set to publish next available slot
            await self._schedule_content(content_id)
        except Exception as e:
            await self.notifier.notify_admins(f"❌ 图文合成失败：{content_id}\n{e}")

    async def _schedule_content(self, content_id: str) -> None:
        """Mark content as scheduled and notify with schedule card."""
        from datetime import datetime, timedelta, timezone

        # Default: schedule 1 hour from now
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == content_id:
                    await self.bitable.update_record("content", r["record_id"], {
                        "status": ContentStatus.SCHEDULED.value,
                        "scheduled_at": scheduled_at.isoformat(),
                    })
                    break
        except Exception as e:
            logger.warning("schedule update failed: %s", e)

        await self.notifier.notify_admins(
            f"📅 已排期：{content_id}\n发布时间：{scheduled_at.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        # Send schedule card to group
        await self._send_schedule_card()

    async def _send_schedule_card(self) -> None:
        """Fetch all scheduled items from bitable and send schedule card."""
        from app.services.cards import build_schedule_card

        try:
            records = await self.bitable.list_records("content")
            scheduled_items = []
            for r in records:
                fields = r.get("fields", {})
                if fields.get("status") in ("scheduled", "approved", "pending_review"):
                    scheduled_items.append({
                        "topic": fields.get("topic", ""),
                        "platform": fields.get("platform", ""),
                        "scheduled_at": fields.get("scheduled_at", "待定"),
                        "status": fields.get("status", ""),
                    })
            chat_id = self.settings.feishu_default_chat_id
            if chat_id:
                card = build_schedule_card(scheduled_items, self.settings.feishu_bitable_app_token)
                await self.notifier.send_card(chat_id, card)
        except Exception as e:
            logger.warning("send schedule card failed: %s", e)

    async def get_schedule(self) -> dict:
        """Return schedule card for /排期 command."""
        from app.services.cards import build_schedule_card

        try:
            records = await self.bitable.list_records("content")
            scheduled_items = []
            for r in records:
                fields = r.get("fields", {})
                if fields.get("status") in ("scheduled", "approved", "pending_review"):
                    scheduled_items.append({
                        "topic": fields.get("topic", ""),
                        "platform": fields.get("platform", ""),
                        "scheduled_at": fields.get("scheduled_at", "待定"),
                        "status": fields.get("status", ""),
                    })
            return {"status": "ok", "card": build_schedule_card(scheduled_items, self.settings.feishu_bitable_app_token)}
        except Exception:
            return {"status": "ok", "card": build_schedule_card([])}

    async def status_summary(self) -> dict:
        try:
            records = await self.bitable.list_records("content")
            counts: dict[str, int] = {}
            for r in records:
                s = r.get("fields", {}).get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1
            summary = "\n".join(f"- {k}: {v}" for k, v in counts.items()) or "暂无内容"
            card = build_status_card("系统状态", summary)
        except Exception:
            card = build_status_card("系统状态", "多维表未配置，无法读取状态。")
        return {"status": "ok", "card": card}

    async def _run_risk_check(self, job: SkillJob, content_result: dict) -> dict:
        risk_job = SkillJob(
            content_id=job.content_id,
            job_id=f"JOB-RISK-{uuid4().hex[:8]}",
            platform=job.platform,
            topic=job.topic,
            column=job.column,
            materials=[{"type": "generated_content", "payload": content_result.get("data", {})}],
        )
        try:
            return self.runner.run("risk-check", risk_job)
        except (FileNotFoundError, RuntimeError) as e:
            logger.warning("risk-check skipped: %s", e)
            return {"status": "skipped", "data": {"risk_level": "low", "reason": "risk-check unavailable"}}

    async def _persist_content(self, item: ContentItem) -> None:
        try:
            fields = {
                "content_id": item.content_id,
                "platform": item.platform.value,
                "topic": item.topic,
                "status": item.status.value,
            }
            if item.scheduled_at:
                fields["scheduled_at"] = item.scheduled_at.isoformat()
            await self.bitable.create_record("content", fields)
        except Exception as e:
            logger.warning("bitable persist failed (non-fatal): %s", e)

    async def _update_content_status(self, content_id: str, status: ContentStatus) -> None:
        try:
            records = await self.bitable.list_records("content")
            for r in records:
                if r.get("fields", {}).get("content_id") == content_id:
                    await self.bitable.update_record("content", r["record_id"], {"status": status.value})
                    return
        except Exception as e:
            logger.warning("bitable update failed (non-fatal): %s", e)

    def _skill_for_platform(self, platform: Platform) -> str:
        return {
            Platform.XHS: "content-generate-xhs",
            Platform.WECHAT: "content-generate-wechat",
            Platform.DOUYIN: "content-generate-douyin",
        }[platform]
