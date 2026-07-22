from fastapi.testclient import TestClient

from app.config import get_settings
from app.api.health import _compare_content_schema
from app.main import create_app


def test_runtime_health_exposes_safe_deployment_facts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SKILL_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_BUILD_SHA", "1234567890abcdef")
    monkeypatch.setenv("AGENT_RECOVERY_ENABLED", "false")
    monkeypatch.setenv("FEISHU_APP_ID", "app-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret-value")
    monkeypatch.setenv("WECHAT_APP_ID", "")
    monkeypatch.setenv("WECHAT_APP_SECRET", "")
    (tmp_path / "jobs" / "JOB-1").mkdir(parents=True)
    get_settings.cache_clear()

    data = TestClient(create_app()).get("/health/runtime").json()

    assert data["workflow_engine"] == "agent_loop"
    assert data["legacy_card_actions"] == "deprecated"
    assert data["agent_recovery_enabled"] is False
    assert data["build"]["commit"] == "1234567890ab"
    assert data["storage"]["job_count"] == 1
    assert data["configuration"]["feishu"] is True
    assert data["configuration"]["wechat_draft"] is False
    assert "secret-value" not in str(data)

    get_settings.cache_clear()


def test_content_schema_diagnostic_lists_missing_and_wrong_fields() -> None:
    result = _compare_content_schema(
        [
            {"field_name": "content_id", "type": 1, "ui_type": "Text"},
            {"field_name": "created_at", "type": 1, "ui_type": "Text"},
        ]
    )

    assert result["compatible"] is False
    assert "image_result" in result["missing_fields"]
    assert result["type_mismatches"] == [
        {
            "field": "created_at",
            "actual_type": 1,
            "actual_ui_type": "Text",
            "expected_types": [5],
        }
    ]
