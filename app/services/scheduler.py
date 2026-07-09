import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.models import ContentStatus, Platform

logger = logging.getLogger(__name__)


class SchedulableStore(Protocol):
    async def list_records(self, table_key: str) -> list[dict]: ...

    async def update_record(self, table_key: str, record_id: str, fields: dict) -> dict: ...


async def scheduler_tick(store: SchedulableStore, now: datetime | None = None) -> list[str]:
    """Check for due content and mark as publishing."""
    current = now or datetime.now(timezone.utc)
    triggered: list[str] = []
    for record in await store.list_records("content"):
        fields = record.get("fields", {})
        status = fields.get("status")
        scheduled_at = fields.get("scheduled_at")
        if status != ContentStatus.SCHEDULED.value or not scheduled_at:
            continue
        due_at = datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
        if due_at <= current:
            record_id = record.get("record_id")
            if record_id:
                await store.update_record("content", record_id, {"status": "publishing"})
                triggered.append(fields.get("content_id", record_id))
    return triggered


async def publish_due_content(settings, store: SchedulableStore, notifier) -> list[dict]:
    """Full publish tick: find due items, publish via social-auto-upload, update status."""
    from app.services.publisher import Publisher, PublishPayload

    triggered_ids = await scheduler_tick(store)
    if not triggered_ids:
        return []

    publisher = Publisher(settings)
    results = []

    for content_id in triggered_ids:
        # Find generation data
        jobs_dir = settings.data_dir / "jobs"
        gen_data = _find_gen_data(jobs_dir, content_id)
        if not gen_data:
            logger.warning("publish skip: no gen data for %s", content_id)
            results.append({"content_id": content_id, "success": False, "reason": "no gen data"})
            continue

        platform = gen_data.get("platform", "xhs")
        title = gen_data.get("selected_title", gen_data.get("topic", ""))
        body = gen_data.get("body", "")
        hashtags = gen_data.get("hashtags", [])

        # Find cover image
        image_paths = _find_images(jobs_dir, content_id)

        payload = PublishPayload(
            platform=platform,
            account="default",
            title=title,
            body=body,
            tags=hashtags,
            image_paths=image_paths,
        )

        pub_result = publisher.publish(payload)
        results.append({
            "content_id": content_id,
            "success": pub_result.success,
            "message": pub_result.message,
        })

        # Update bitable status
        new_status = "published" if pub_result.success else "publish_failed"
        records = await store.list_records("content")
        for r in records:
            if r.get("fields", {}).get("content_id") == content_id:
                await store.update_record("content", r["record_id"], {"status": new_status})
                break

        # Notify
        if pub_result.success:
            await notifier.notify_admins(f"✅ 已发布：{title} ({platform})")
        else:
            await notifier.notify_admins(f"❌ 发布失败：{title} ({platform})\n{pub_result.message}")

    return results


def _find_gen_data(jobs_dir: Path, content_id: str) -> dict | None:
    if not jobs_dir.exists():
        return None
    for job_dir in sorted(jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        for f in job_dir.glob("content-generate-*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("content_id") == content_id:
                    return data
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _find_images(jobs_dir: Path, content_id: str) -> list[str]:
    if not jobs_dir.exists():
        return []
    for job_dir in sorted(jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if content_id[4:] in job_dir.name:
            output_dir = job_dir / "output"
            if output_dir.exists():
                return [str(p) for p in output_dir.glob("*.png")]
    return []
