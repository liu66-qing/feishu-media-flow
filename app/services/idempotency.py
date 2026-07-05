import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class IdempotencyStore:
    def __init__(self, path: Path, ttl_hours: int = 24) -> None:
        self.path = path
        self.ttl = timedelta(hours=ttl_hours)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def seen_or_record(self, event_id: str) -> bool:
        if not event_id:
            return False
        records = self._load()
        now = datetime.now(timezone.utc)
        cutoff = now - self.ttl
        records = {key: value for key, value in records.items() if datetime.fromisoformat(value) >= cutoff}
        if event_id in records:
            self._save(records)
            return True
        records[event_id] = now.isoformat()
        self._save(records)
        return False

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, records: dict[str, str]) -> None:
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

