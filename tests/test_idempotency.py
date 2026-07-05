from app.services.idempotency import IdempotencyStore


def test_seen_or_record(tmp_path) -> None:
    store = IdempotencyStore(tmp_path / "events.json")
    assert store.seen_or_record("evt") is False
    assert store.seen_or_record("evt") is True

