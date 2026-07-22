import hashlib
import os

from fastapi import APIRouter

from app.config import get_settings
from app.services.bitable import BitableClient

router = APIRouter()

_CONTENT_FIELD_SCHEMA = {
    "content_id": {1},
    "topic_id": {1},
    "topic": {1},
    "platform": {1, 3},
    "target_platforms": {1},
    "status": {1, 3},
    "version": {2},
    "revision_count": {2},
    "content_payload": {1},
    "key_points": {1},
    "critic_feedback": {1},
    "scheduled_at": {5},
    "created_at": {5},
    "materials": {1},
    "chat_id": {1},
    "image_result": {1},
    "package_result": {1},
    "reviewed_by": {1},
    "reviewed_at": {5},
    "profile_version": {1},
    "preference_profile": {1},
    "post_id": {1},
    "post_url": {1, 15},
    "published_at": {5},
    "metrics_snapshots": {1},
    "metrics_attempts": {1},
}


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "env": settings.app_env}


@router.get("/health/runtime")
def runtime_health() -> dict:
    """Expose non-secret deployment facts for version and storage diagnosis."""
    settings = get_settings()
    jobs_dir = settings.data_dir / "jobs"
    commit = _first_env(
        "APP_BUILD_SHA",
        "RENDER_GIT_COMMIT",
        "RAILWAY_GIT_COMMIT_SHA",
        "VERCEL_GIT_COMMIT_SHA",
        "GITHUB_SHA",
    )
    hostname = _first_env("HOSTNAME", "COMPUTERNAME") or "unknown"
    instance_id = hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:12]

    return {
        "status": "ok",
        "workflow_engine": "agent_loop",
        "agent_recovery_enabled": settings.agent_recovery_enabled,
        "legacy_card_actions": "deprecated",
        "build": {
            "commit": commit[:12] if commit else "unknown",
            "app_version": "0.3.0",
        },
        "instance_id": instance_id,
        "storage": {
            "data_dir_exists": settings.data_dir.exists(),
            "data_dir_writable": os.access(settings.data_dir, os.W_OK),
            "jobs_dir_exists": jobs_dir.exists(),
            "job_count": sum(1 for path in jobs_dir.iterdir() if path.is_dir()) if jobs_dir.exists() else 0,
        },
        "configuration": {
            "feishu": bool(settings.feishu_app_id and settings.feishu_app_secret),
            "bitable_content": bool(settings.feishu_bitable_app_token and settings.feishu_table_content),
            "wechat_draft": bool(settings.wechat_app_id and settings.wechat_app_secret),
            "xhs_publish_account": bool(settings.social_auto_upload_default_account),
        },
        "components": {
            "content_generate_xhs": _skill_exists(settings, "content-generate-xhs"),
            "content_generate_douyin": _skill_exists(settings, "content-generate-douyin"),
            "content_generate_wechat": _skill_exists(settings, "content-generate-wechat"),
            "image_compose": _skill_exists(settings, "image-compose"),
            "xhs_publish_package": _skill_exists(settings, "xhs-publish-package"),
            "platform_sample_collector": _skill_exists(settings, "platform-sample-collector"),
            "platform_preference_profiler": _skill_exists(settings, "platform-preference-profiler"),
            "platform_metrics_collector": _skill_exists(settings, "platform-metrics-collector"),
            "social_auto_upload": (settings.skill_root / "vendor" / "social-auto-upload" / "sau_cli.py").exists(),
        },
    }


@router.get("/health/bitable")
async def bitable_health() -> dict:
    """Compare the configured content table with the AgentLoop field contract."""
    settings = get_settings()
    if not settings.feishu_bitable_app_token or not settings.feishu_table_content:
        return {
            "status": "not_configured",
            "compatible": False,
            "missing_fields": sorted(_CONTENT_FIELD_SCHEMA),
            "type_mismatches": [],
        }
    try:
        fields = await BitableClient(settings).list_fields("content")
    except Exception as exc:
        return {
            "status": "error",
            "compatible": False,
            "error": str(exc)[:500],
        }
    result = _compare_content_schema(fields)
    return {"status": "ok", **result}


def _skill_exists(settings, skill_name: str) -> bool:
    return (settings.skill_root / skill_name / "main.py").exists()


def _first_env(*names: str) -> str:
    return next((value for name in names if (value := os.getenv(name, "").strip())), "")


def _compare_content_schema(fields: list[dict]) -> dict:
    actual = {str(field.get("field_name", "")): field for field in fields}
    missing = sorted(name for name in _CONTENT_FIELD_SCHEMA if name not in actual)
    mismatches = []
    for name, expected_types in _CONTENT_FIELD_SCHEMA.items():
        if name not in actual:
            continue
        actual_type = actual[name].get("type")
        if actual_type not in expected_types:
            mismatches.append(
                {
                    "field": name,
                    "actual_type": actual_type,
                    "actual_ui_type": actual[name].get("ui_type", ""),
                    "expected_types": sorted(expected_types),
                }
            )
    return {
        "compatible": not missing and not mismatches,
        "field_count": len(actual),
        "missing_fields": missing,
        "type_mismatches": mismatches,
    }
