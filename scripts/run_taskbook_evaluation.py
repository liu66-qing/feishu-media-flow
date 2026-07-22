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
        "topic": "大学社团招新：如何让新生愿意停下来并留下联系方式",
        "column": "校园新媒体运营",
        "materials": [
            {"fact": "招新摊位不能只发传单，要设计一个30秒体验点", "source_url": "https://example.com/taskbook/material-1"},
            {"fact": "新生最关心交友、技能和时间投入", "source_url": "https://example.com/taskbook/material-2"},
            {"fact": "现场准备三个问题：想认识谁、想学什么、每周能投入多久", "source_url": "https://example.com/taskbook/material-3"},
            {"fact": "扫码后立即提供活动清单和首次见面会时间", "source_url": "https://example.com/taskbook/material-4"},
        ],
        "brand": {"tone": "真诚、年轻、实用", "audience": "新生与社团干部"},
        "target_length": 1200,
        "preference_profile": profile,
        "profile_version": str(profile.get("v") or profile.get("gen_at") or "static"),
    }


def output_payload(job_dir: Path, filename: str) -> dict[str, Any]:
    path = job_dir / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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

    fixture = json.loads(
        (ROOT / "platform-sample-collector" / "test" / "fixtures" / "job1" / "input.json").read_text(encoding="utf-8")
    )
    samples_dir = run_dir / "data" / "samples"
    fixture["samples_dir"] = str(samples_dir)
    sample_check, sample_job = run_skill(
        "platform_samples", "platform-sample-collector", fixture, outputs_dir, logs_dir
    )
    checks.append(sample_check)

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
                "ai_prompt": title,
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
        "target_column": "校园运营经验",
        "rewrite_angle": "从新生决策成本切入",
        "source": {
            "title": "社团招新怎么让新生停下来",
            "url": "https://example.com/taskbook/source",
            "content": "社团招新摊位如果只发传单，新生很难理解加入后的体验。可以设计三十秒互动，围绕交友、技能和时间投入提问，并在扫码后立即提供活动清单与首次见面会时间。表达应真实，不夸大收益。",
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
