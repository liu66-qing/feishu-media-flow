from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def setup_function() -> None:
    get_settings.cache_clear()


def test_url_verification(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "token")
    client = TestClient(create_app())
    response = client.post("/feishu/webhook", json={"type": "url_verification", "token": "token", "challenge": "abc"})
    assert response.status_code == 200
    assert response.json() == {"challenge": "abc"}


def test_duplicate_event_is_ignored(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FEISHU_ENCRYPT_KEY", "")
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "")
    payload = {
        "header": {"event_id": "evt-1", "event_type": "im.message.receive_v1"},
        "event": {"message": {"content": "{\"text\":\"hello\"}"}},
    }
    client = TestClient(create_app())
    assert client.post("/feishu/webhook", json=payload).json()["status"] == "ignored"
    assert client.post("/feishu/webhook", json=payload).json()["status"] == "duplicate"


def test_create_command_enters_agent_loop(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SKILL_ROOT", str(tmp_path / "missing-skills"))
    monkeypatch.setenv("FEISHU_ENCRYPT_KEY", "")
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "")
    payload = {
        "header": {"event_id": "evt-2", "event_type": "im.message.receive_v1"},
        "event": {"message": {"content": "{\"text\":\"/新建 小红书 社团招新方法\"}"}},
    }
    client = TestClient(create_app())
    data = client.post("/feishu/webhook", json=payload).json()
    assert data == {"status": "accepted", "topic": "社团招新方法"}


def test_legacy_card_action_is_not_routed_to_workflow_service(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FEISHU_ENCRYPT_KEY", "")
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "")
    payload = {
        "header": {"event_id": "evt-3", "event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "ou_1"},
            "action": {"value": {"action": "approve_all", "content_ids": ["CNT-1", "CNT-2"]}},
        },
    }
    client = TestClient(create_app())
    data = client.post("/feishu/webhook", json=payload).json()
    assert data["status"] == "deprecated_action"
    assert data["action"] == "approve_all"

