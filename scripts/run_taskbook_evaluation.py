"""Run a reproducible taskbook-focused evaluation and package the evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("wechat", "douyin", "xhs")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(name: str, command: list[str], cwd: Path, logs_dir: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    (logs_dir / f"{name}.stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    (logs_dir / f"{name}.stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    return {"name": name, "returncode": completed.returncode, "ok": completed.returncode == 0}


def run_skill(
    name: str,
    skill_dir: str,
    input_data: dict[str, Any],
    outputs_dir: Path,
    logs_dir: Path,
) -> tuple[dict[str, Any], Path]:
    job_dir = outputs_dir / name
    job_dir.mkdir(parents=True, exist_ok=True)
    write_json(job_dir / "input.json", input_data)
    result = run_command(
        name,
        [sys.executable, str(ROOT / skill_dir / "main.py"), "--job-dir", str(job_dir)],
        ROOT,
        logs_dir,
    )
    return result, job_dir


def base_input(platform: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": f"EVAL-{platform.upper()}-001",
        "job_id": f"JOB-EVAL-{platform.upper()}-001",
        "platform": platform,
        "topic": "AI时代，只走课程和证书路线的准大一，如何建立不会被轻易替代的项目能力",
        "column": "TYUT创新学社·AI成长路线",
        "materials": [
            {"fact": "TYUT创新学社面向太原理工大学准大一和低年级学生，聚焦AI科研与应用实践", "source_url": "local://app/strategy/tyut_innovation.json"},
            {"fact": "不要求技术基础，但要求按时提交、保留过程记录、根据反馈修改并持续完成任务", "source_url": "local://app/strategy/tyut_innovation.json"},
            {"fact": "成员依据任务完成质量从L0逐步晋级到L3，不设置人数上限", "source_url": "local://app/strategy/tyut_innovation.json"},
            {"fact": "Line1文档智能与知识库、Line2 GUI Agent、Line3 Self-Research以论文与研究成果为主", "source_url": "local://app/strategy/tyut_innovation.json"},
            {"fact": "Line4 OSINT与多媒体运营Agent以系统实践、运营实验和数据反馈为主", "source_url": "local://app/strategy/tyut_innovation.json"},
            {"fact": "主要转化动作是进入招新群，二维码仅在发布前人工替换", "source_url": "local://app/strategy/tyut_innovation.json"},
        ],
        "brand": {"name": "TYUT创新学社", "tone": "克制、有张力、技术可信、不给零基础贴标签", "audience": "对AI时代个人价值和能力路径感到不确定的准大一", "school_tag": "#太原理工大学"},
        "target_length": 1200,
        "preference_profile": profile,
        "profile_version": str(profile.get("v") or profile.get("gen_at") or "static"),
    }


def output_payload(job_dir: Path, filename: str) -> dict[str, Any]:
    path = job_dir / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_reviewed_sample_fixture(seed_fixture: dict[str, Any]) -> dict[str, Any]:
    """Expand repository seeds into a labeled schema fixture for the quality gate.

    These are not presented as live platform observations. Their only purpose is to
    prove that shortlist/core separation, visual fields and profile eligibility work.
    """
    seeds = seed_fixture.get("samples", [])
    by_platform = {platform: [item for item in seeds if item.get("platform") == platform] for platform in PLATFORMS}
    reviewed: list[dict[str, Any]] = []
    for platform in PLATFORMS:
        platform_seeds = by_platform.get(platform) or [{"title": f"{platform} AI成长路线", "summary": "准大一AI项目能力"}]
        for index in range(10):
            item = dict(platform_seeds[index % len(platform_seeds)])
            item.update({
                "sample_id": f"EVAL-{platform.upper()}-{index + 1:02d}",
                "platform": platform,
                "title": f"准大一AI项目能力：{item.get('title', '')}",
                "summary": f"AI时代个人价值、科研与真实项目路径。{item.get('summary', '')}",
                "source_url": f"https://example.com/evaluation-fixture/{platform}/{index + 1}",
                "published_at": "2026-07-22T00:00:00Z",
                "data_status": "fixture_not_real_traffic",
                "manual_review": "approved",
                "cover": f"https://example.com/evaluation-fixture/{platform}/{index + 1}.png",
                "cover_analysis": {"composition": "单人物冲突对照", "headline": "AI时代能力差距", "style": "极简手绘", "visual_metaphor": "旧路线与项目路线分岔"},
                "metrics": {"views": 10000 + index * 300, "likes": 700 + index * 20, "comments": 50 + index, "favorites": 260 + index * 8, "shares": 70 + index * 2},
            })
            reviewed.append(item)
    return {**seed_fixture, "samples": reviewed, "keywords": ["准大一", "AI", "项目", "科研"], "max_samples": 100}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(ROOT / "evaluation_runs"))
    parser.add_argument("--ai-image", action="store_true", help="Use configured AI background generation")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_root).resolve() / f"taskbook_{timestamp}"
    logs_dir = run_dir / "logs"
    outputs_dir = run_dir / "outputs"
    meta_dir = run_dir / "meta"
    for directory in (logs_dir, outputs_dir, meta_dir):
        directory.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    checks.append(run_command("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], ROOT, logs_dir))
    for name, command in {
        "git_commit": ["git", "rev-parse", "HEAD"],
        "git_status": ["git", "status", "--short", "--branch"],
        "python_version": [sys.executable, "--version"],
    }.items():
        result = run_command(name, command, ROOT, logs_dir)
        checks.append(result)

    fixture = build_reviewed_sample_fixture(json.loads(
        (ROOT / "platform-sample-collector" / "test" / "fixtures" / "job1" / "input.json").read_text(encoding="utf-8")
    ))
    samples_dir = run_dir / "data" / "samples"
    fixture["samples_dir"] = str(samples_dir)
    sample_check, sample_job = run_skill(
        "platform_samples", "platform-sample-collector", fixture, outputs_dir, logs_dir
    )
    checks.append(sample_check)
    sample_output = output_payload(sample_job, "platform-sample-collector.json")
    checks.append({
        "name": "sample_quality_gate",
        "returncode": 0 if sample_output.get("profile_eligible") else 1,
        "ok": bool(sample_output.get("profile_eligible")),
    })

    profiles_dir = run_dir / "data" / "profiles"
    profiler_input = {
        "content_id": "EVAL-PROFILES-001",
        "job_id": "JOB-EVAL-PROFILES-001",
        "platforms": list(PLATFORMS),
        "samples_dir": str(samples_dir),
        "output_dir": str(profiles_dir),
    }
    profile_check, _ = run_skill(
        "platform_profiles", "platform-preference-profiler", profiler_input, outputs_dir, logs_dir
    )
    checks.append(profile_check)

    generated: dict[str, dict[str, Any]] = {}
    skill_names = {
        "wechat": "content-generate-wechat",
        "douyin": "content-generate-douyin",
        "xhs": "content-generate-xhs",
    }
    output_names = {
        "wechat": "content-generate-wechat.json",
        "douyin": "content-generate-douyin.json",
        "xhs": "content-generate-xhs.json",
    }
    for platform in PLATFORMS:
        profile_path = profiles_dir / f"{platform}_profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
        check, job_dir = run_skill(
            f"content_{platform}", skill_names[platform], base_input(platform, profile), outputs_dir, logs_dir
        )
        checks.append(check)
        generated[platform] = output_payload(job_dir, output_names[platform])

        payload = generated[platform].get("data", generated[platform])
        title = str(payload.get("selected_title") or payload.get("title") or "校园社团招新")
        image_input = {
            "content_id": f"EVAL-IMAGE-{platform.upper()}",
            "job_id": f"JOB-EVAL-IMAGE-{platform.upper()}",
            "platform": platform,
            "image_mode": "ai_bg" if args.ai_image else "template",
            "template_name": "",
            "variables": {
                "title": str(payload.get("cover_text") or title[:20]),
                "subtitle": title,
                "visual_style": "auto",
                "template_role": "cover",
                "ai_prompt": f"{title}；极简手绘简笔画；AI时代个人价值的视觉隐喻；不生成文字；TYUT深蓝与青蓝品牌色",
                "brand_name": "TYUT创新学社",
                "series_name": "AI成长路线",
            },
            "output_size": {"width": 1080, "height": 1350},
            "preference_profile": profile,
            "profile_version": str(profile.get("v") or profile.get("gen_at") or "static"),
        }
        image_check, _ = run_skill(
            f"image_{platform}", "image-compose", image_input, outputs_dir, logs_dir
        )
        checks.append(image_check)

    rewrite_input = {
        "content_id": "EVAL-REWRITE-001",
        "job_id": "JOB-EVAL-REWRITE-001",
        "target_platform": "xhs",
        "target_column": "AI成长路线",
        "rewrite_angle": "从AI时代个人价值与被动成长路线的不确定性切入",
        "source": {
            "title": "准大一如何建立AI时代的项目能力",
            "url": "https://example.com/taskbook/source",
            "content": "TYUT创新学社不要求新生已有技术基础，而是通过L0任务观察是否能按时提交、保留过程、根据反馈修改。成员可进入文档智能、GUI Agent、Self-Research或OSINT与多媒体运营Agent四条线路，并按交付质量逐级晋级。内容不得承诺保研就业，也不能虚构被AI淘汰的后果。",
        },
    }
    rewrite_check, _ = run_skill("hot_rewrite", "hot-rewrite", rewrite_input, outputs_dir, logs_dir)
    checks.append(rewrite_check)

    metrics_input = {
        "content_id": "EVAL-METRICS-001",
        "job_id": "JOB-EVAL-METRICS-001",
        "platform": "xhs",
        "checkpoint": "6h",
        "post_id": "evaluation-only",
        "post_url": "https://example.com/evaluation-only",
        "data_status": "manual_verified",
        "metrics_source": "evaluation_fixture_not_real_publish_data",
        "metrics": {"impressions": 2380, "views": 1910, "likes": 126, "comments": 18, "favorites": 47, "shares": 12, "followers_gained": 9},
        "experiment": {"variable": "cover", "variant": "high_contrast"},
    }
    metrics_check, _ = run_skill(
        "metrics_schema", "platform-metrics-collector", metrics_input, outputs_dir, logs_dir
    )
    checks.append(metrics_check)

    summary = {
        "run_id": run_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ai_image_requested": bool(args.ai_image),
        "checks": checks,
        "passed": sum(1 for item in checks if item["ok"]),
        "failed": sum(1 for item in checks if not item["ok"]),
        "notes": [
            "metrics_schema uses labeled fixture numbers only to validate the schema; it is not real publish performance.",
            "Live/cache/degraded state must be read from each collector output before drawing conclusions.",
            "sample_quality_gate uses clearly labeled synthetic fixtures to validate 10 core samples per platform; it is not evidence of real traffic performance.",
        ],
    }
    write_json(meta_dir / "summary.json", summary)
    archive_path = run_dir.with_suffix(".tar.gz")
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(run_dir, arcname=run_dir.name)
    print(json.dumps({"run_dir": str(run_dir), "archive": str(archive_path), **summary}, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
