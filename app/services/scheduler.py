from datetime import datetime, timezone
from typing import Protocol

from app.models import ContentStatus


class SchedulableStore(Protocol):
    async def list_records(self, table_key: str) -> list[dict]: ...

    async def update_record(self, table_key: str, record_id: str, fields: dict) -> dict: ...


async def scheduler_tick(store: SchedulableStore, now: datetime | None = None) -> list[str]:
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
                await store.update_record("content", record_id, {"status": ContentStatus.APPROVED.value})
                triggered.append(record_id)
    return triggered

