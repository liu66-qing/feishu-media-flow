from datetime import datetime, timezone

from app.services.scheduler import scheduler_tick


class FakeStore:
    def __init__(self) -> None:
        self.updated = []

    async def list_records(self, table_key: str) -> list[dict]:
        assert table_key == "content"
        return [
            {"record_id": "rec_due", "fields": {"status": "scheduled", "scheduled_at": "2026-07-05T00:00:00+00:00"}},
            {"record_id": "rec_later", "fields": {"status": "scheduled", "scheduled_at": "2026-07-06T00:00:00+00:00"}},
            {"record_id": "rec_draft", "fields": {"status": "draft"}},
        ]

    async def update_record(self, table_key: str, record_id: str, fields: dict) -> dict:
        self.updated.append((table_key, record_id, fields))
        return {"ok": True}


async def test_scheduler_tick_triggers_due_records() -> None:
    store = FakeStore()
    triggered = await scheduler_tick(store, datetime(2026, 7, 5, 1, tzinfo=timezone.utc))
    assert triggered == ["rec_due"]
    assert store.updated == [("content", "rec_due", {"status": "publishing"})]
