import asyncio
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import Platform
from app.services.agent_loop import AgentLoop, _next_due_checkpoint
from app.services.analytics import build_weekly_performance_report
from app.services.cards import build_material_review_card, build_video_review_card
from app.services.publisher import _extract_publish_metadata


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeBitable:
    def __init__(self):
        self.records = []
        self.created = []
        self.updated = []

    async def create_record(self, table, fields):
        self.created.append((table, dict(fields)))
        record = {"record_id": f"rec-{len(self.records) + 1}", "fields": dict(fields)}
        self.records.append(record)
        return record

    async def list_records(self, table):
        return self.records if table == "content" else []

    async def update_record(self, table, record_id, fields):
        self.updated.append((table, record_id, dict(fields)))
        for record in self.records:
            if record["record_id"] == record_id:
                record["fields"].update(fields)
        return {}


class NoopNotifier:
    async def notify_admins(self, message):
        return None

    async def send_card(self, chat_id, card):
        return None


class TopicRunner:
    def __init__(self):
        self.job = None

    def run(self, skill_name, job):
        self.job = job
        return {
            "topics": [
                {
                    "title": "校园社团招新体验点",
                    "source": "xhs",
                    "source_url": "https://example.com/note/1",
                    "heat_score": 88,
                    "relevance_score": 0.91,
                    "angle_suggestion": "拆解30秒互动",
                    "suggested_platform": "xhs",
                    "data_status": "live",
                    "collected_at": "2026-07-22T00:00:00Z",
                }
            ]
        }


def test_material_card_preserves_traceability_fields():
    topic = {
        "material_id": "MAT-1",
        "title": "校园社团招新体验点",
        "source": "xhs",
        "source_url": "https://example.com/note/1",
        "heat_score": 88,
        "relevance_score": 0.91,
        "angle_suggestion": "拆解30秒互动",
        "suggested_platform": "xhs",
        "data_status": "live",
        "collected_at": "2026-07-22T00:00:00Z",
    }
    card = build_material_review_card([topic])
    button = next(item for item in card["elements"] if item["tag"] == "action")["actions"][0]
    assert button["value"]["material_id"] == "MAT-1"
    assert button["value"]["source_url"] == topic["source_url"]
    assert button["value"]["heat_score"] == 88
    assert "数据状态：live" in card["elements"][0]["text"]["content"]


@pytest.mark.asyncio
async def test_adopt_topic_passes_complete_material(tmp_path):
    agent = AgentLoop(
        Settings(data_dir=tmp_path, skill_root=ROOT),
        bitable=FakeBitable(),
        notifier=NoopNotifier(),
    )
    captured = {}

    async def fake_create(platform, topic, *, chat_id="", materials=None):
        captured.update(platform=platform, topic=topic, materials=materials)
        return {"status": "created"}

    agent.create_content_from_topic = fake_create
    result = await agent.handle_card_action(
        {
            "action": "adopt_topic",
            "topic_title": "校园社团招新体验点",
            "platform": "xhs",
            "angle": "拆解30秒互动",
            "material_id": "MAT-1",
            "source": "xhs",
            "source_url": "https://example.com/note/1",
            "heat_score": 88,
            "data_status": "live",
        }
    )
    await asyncio.sleep(0)
    assert result["status"] == "accepted"
    assert captured["materials"][0]["source_url"] == "https://example.com/note/1"
    assert captured["materials"][0]["angle_suggestion"] == "拆解30秒互动"


@pytest.mark.asyncio
async def test_weekly_collector_receives_real_job_fields_and_persists(tmp_path):
    bitable = FakeBitable()
    runner = TopicRunner()
    settings = Settings(
        data_dir=tmp_path,
        skill_root=ROOT,
        feishu_table_materials="tbl-materials",
    )
    agent = AgentLoop(settings, bitable=bitable, notifier=NoopNotifier(), runner=runner)
    topics = await agent._collect_weekly_topics()
    assert runner.job.keywords
    assert runner.job.platforms == ["weibo", "douyin", "xhs"]
    assert runner.job.max_topics == 10
    assert topics[0]["material_id"].startswith("MAT-")
    assert bitable.created[0][0] == "materials"
    assert bitable.created[0][1]["data_status"] == "live"


def test_metrics_collector_keeps_source_status_and_all_dimensions():
    module = load_module(
        "platform_metrics_test", ROOT / "platform-metrics-collector" / "main.py"
    )
    result = module.generate_result(
        {
            "content_id": "CNT-1",
            "platform": "xhs",
            "checkpoint": "6h",
            "post_id": "note-1",
            "post_url": "https://example.com/note-1",
            "data_status": "manual_verified",
            "metrics_source": "creator-center-export",
            "metrics": {"exposure": 1200, "likes": 80, "collects": 21},
        }
    )
    snapshot = result["snapshot"]
    assert snapshot["metrics"]["impressions"] == 1200
    assert snapshot["metrics"]["favorites"] == 21
    assert snapshot["metrics_source"] == "creator-center-export"
    assert set(snapshot["metrics"]) == set(module.METRIC_FIELDS)


def test_metrics_collector_never_presents_missing_data_as_live():
    module = load_module(
        "platform_metrics_missing_test", ROOT / "platform-metrics-collector" / "main.py"
    )
    result = module.generate_result(
        {"content_id": "CNT-1", "platform": "xhs", "checkpoint": "1h"}
    )
    assert result["status"] == "degraded"
    assert result["snapshot"]["data_status"] == "unavailable"


def test_checkpoint_sequence_is_time_based_and_deduplicated():
    published_at = datetime.now(timezone.utc) - timedelta(hours=26)
    fields = {
        "published_at": int(published_at.timestamp() * 1000),
        "metrics_snapshots": json.dumps([{"checkpoint": "1h"}, {"checkpoint": "6h"}]),
    }
    assert _next_due_checkpoint(fields) == "24h"


def test_unavailable_metrics_are_throttled_instead_of_retried_every_tick():
    now = datetime.now(timezone.utc)
    fields = {
        "published_at": int((now - timedelta(hours=2)).timestamp() * 1000),
        "metrics_snapshots": "[]",
        "metrics_attempts": json.dumps(
            [{"checkpoint": "1h", "observed_at": now.isoformat(), "data_status": "unavailable"}]
        ),
    }
    assert _next_due_checkpoint(fields, now=now) == ""


def test_hot_rewrite_rejects_empty_or_too_short_source():
    module = load_module("hot_rewrite_validation_test", ROOT / "hot-rewrite" / "main.py")
    with pytest.raises(ValueError, match="at least 50"):
        module.generate_hot_rewrite({"source": {"title": "只有标题", "content": "太短"}})


def test_publish_metadata_is_extracted_from_cli_json():
    metadata = _extract_publish_metadata(
        'upload complete\n{"note_id":"abc123","share_url":"https://xhs.example/explore/abc123"}'
    )
    assert metadata["post_id"] == "abc123"
    assert metadata["post_url"].endswith("abc123")
    assert metadata["published_at"]


def test_video_review_card_contains_required_actions():
    card = build_video_review_card(
        "CNT-1", "社团招新", "完整脚本", "img-key", "https://example.com/video.mp4", 63
    )
    actions = next(item for item in card["elements"] if item["tag"] == "action")["actions"]
    assert [item["text"]["content"] for item in actions] == ["下载视频", "通过发布", "打回重新生成"]


def test_weekly_report_separates_observation_from_hypothesis():
    observed_at = datetime.now(timezone.utc).isoformat()
    records = [
        {
            "fields": {
                "content_id": "CNT-1",
                "platform": "xhs",
                "metrics_snapshots": json.dumps(
                    [
                        {
                            "content_id": "CNT-1",
                            "platform": "xhs",
                            "checkpoint": "24h",
                            "observed_at": observed_at,
                            "data_status": "manual_verified",
                            "metrics": {"impressions": 1000, "likes": 50},
                        },
                        {
                            "content_id": "CNT-1",
                            "platform": "xhs",
                            "checkpoint": "72h",
                            "observed_at": observed_at,
                            "data_status": "fallback",
                            "metrics": {"impressions": 999999},
                        },
                    ]
                ),
            }
        }
    ]
    report = build_weekly_performance_report(records)
    assert report["observations"][0]["totals"]["impressions"] == 1000
    assert report["verified_patterns"] == []
    assert report["hypotheses"][0]["status"] == "待验证"
    assert report["excluded_snapshots"][0]["reason"] == "unverified_data_status:fallback"


def test_generator_prompt_uses_injected_profile_instead_of_only_global_file():
    module = load_module("xhs_profile_injection_test", ROOT / "content-generate-xhs" / "main.py")
    prompt = module.build_system_prompt(
        {
            "v": "2026-W30",
            "conf": 0.82,
            "s_cnt": 18,
            "lang": {"tone": "第一人称经验复盘"},
            "s_ids": ["SMP-1"],
        }
    )
    assert "第一人称经验复盘" in prompt
    assert "样本数：18" in prompt


def test_image_contrast_guard_detects_unreadable_white_on_off_white():
    module = load_module("image_contrast_test", ROOT / "image-compose" / "main.py")
    assert module._contrast_ratio("#F7F4EE", "#FFFFFF") < 4.5
    assert module._contrast_ratio("#F7F4EE", "#1F2937") >= 4.5


def test_sample_collector_only_keeps_traceable_samples_and_writes_library(tmp_path, monkeypatch):
    module = load_module(
        "platform_sample_acceptance_test", ROOT / "platform-sample-collector" / "main.py"
    )
    monkeypatch.setattr(module, "CACHE_PATH", tmp_path / "missing-cache.json")
    result = module.generate_result(
        {
            "platforms": ["xhs"],
            "keywords": ["准大一", "AI"],
            "samples": [
                {
                    "platform": "xhs",
                    "title": "准大一如何进入AI项目",
                    "summary": "人工智能时代的项目能力与科研路线",
                    "source_url": "https://example.com/traceable",
                    "data_status": "live",
                    "published_at": "2026-07-22T00:00:00Z",
                    "cover": "https://example.com/cover.png",
                    "cover_analysis": {"composition": "单人物对照", "headline": "AI时代", "style": "手绘"},
                    "metrics": {"views": 1000, "likes": 100, "comments": 20, "favorites": 40},
                },
                {
                    "platform": "xhs",
                    "title": "无来源社团内容",
                    "summary": "校园社团",
                    "data_status": "live",
                },
            ],
        }
    )
    assert result["valid_count"] == 1
    assert result["samples"][0]["sample_id"].startswith("SMP-")
    assert result["samples"][0]["source_url"]
    assert result["samples"][0]["quality_status"] == "machine_shortlist"
    assert set(result["samples"][0]["score_breakdown"]) == {
        "evidence", "audience_fit", "engagement", "visual", "transferability", "anomaly_penalty"
    }


def test_sample_collector_requires_manual_core_pool_for_formal_profile(monkeypatch, tmp_path):
    module = load_module("platform_sample_core_test", ROOT / "platform-sample-collector" / "main.py")
    monkeypatch.setattr(module, "CACHE_PATH", tmp_path / "missing-cache.json")
    sample = {
        "platform": "xhs", "title": "准大一AI路线", "summary": "AI时代项目能力焦虑与解法",
        "source_url": "https://example.com/core", "published_at": "2026-07-22", "data_status": "manual_verified",
        "manual_review": "approved", "cover": "https://example.com/c.png",
        "cover_analysis": {"composition": "冲突对照", "headline": "别只考证", "visual_metaphor": "路线分岔"},
        "metrics": {"views": 10000, "likes": 800, "comments": 60, "favorites": 300, "shares": 80},
    }
    result = module.generate_result({"platforms": ["xhs"], "keywords": ["准大一", "AI"], "samples": [sample] * 12})
    assert result["core_by_platform"]["xhs"] == 1  # duplicate URLs never inflate evidence
    assert result["profile_eligible"] is False


def test_tyut_strategy_has_four_lines_and_ethical_psychology_model():
    strategy = json.loads((ROOT / "app" / "strategy" / "tyut_innovation.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in strategy["lines"]] == ["Line1", "Line2", "Line3", "Line4"]
    assert strategy["brand"]["conversion"] == "进入招新群"
    assert "不虚构淘汰后果" in strategy["psychology_model"]["guardrails"]
