"""Collect and normalize post-performance snapshots without inventing metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


OUTPUT_NAME = "platform-metrics-collector.json"
METRIC_FIELDS = (
    "impressions",
    "views",
    "reads",
    "likes",
    "comments",
    "favorites",
    "shares",
    "followers_gained",
)
CHECKPOINT_HOURS = {"1h": 1, "6h": 6, "24h": 24, "72h": 72}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def normalize_metrics(raw: dict[str, Any] | None) -> dict[str, int]:
    raw = raw or {}
    aliases = {
        "impressions": ("impressions", "exposure", "exposures"),
        "views": ("views", "plays", "play_count"),
        "reads": ("reads", "read_count"),
        "likes": ("likes", "like_count"),
        "comments": ("comments", "comment_count"),
        "favorites": ("favorites", "collects", "favorite_count"),
        "shares": ("shares", "share_count", "forwards"),
        "followers_gained": ("followers_gained", "new_followers", "fans_delta"),
    }
    return {
        field: safe_int(next((raw.get(alias) for alias in names if alias in raw), 0))
        for field, names in aliases.items()
    }


def fetch_endpoint(url: str, input_data: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        url,
        params={
            "platform": input_data.get("platform", ""),
            "post_id": input_data.get("post_id", ""),
            "post_url": input_data.get("post_url", ""),
        },
        timeout=15,
        headers={"User-Agent": "feishu-media-flow/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("metrics endpoint must return a JSON object")
    return payload.get("metrics", payload)


def generate_result(input_data: dict[str, Any]) -> dict[str, Any]:
    content_id = str(input_data.get("content_id") or "").strip()
    platform = str(input_data.get("platform") or "").strip()
    checkpoint = str(input_data.get("checkpoint") or "").strip()
    if not content_id or not platform:
        raise ValueError("content_id and platform are required")
    if checkpoint not in CHECKPOINT_HOURS:
        raise ValueError("checkpoint must be one of 1h, 6h, 24h, 72h")

    raw_metrics = input_data.get("metrics")
    data_status = str(input_data.get("data_status") or "manual")
    source = str(input_data.get("metrics_source") or "input")
    errors: list[str] = []
    endpoint = str(input_data.get("metrics_endpoint") or "").strip()
    if raw_metrics is None and endpoint:
        try:
            raw_metrics = fetch_endpoint(endpoint, input_data)
            data_status = "live"
            source = endpoint
        except Exception as exc:
            errors.append(str(exc))

    if raw_metrics is None:
        data_status = "unavailable"
        source = source if source != "input" else "not_configured"
        raw_metrics = {}

    metrics = normalize_metrics(raw_metrics if isinstance(raw_metrics, dict) else {})
    observed_at = str(input_data.get("observed_at") or now_iso())
    snapshot = {
        "content_id": content_id,
        "platform": platform,
        "post_id": str(input_data.get("post_id") or ""),
        "post_url": str(input_data.get("post_url") or ""),
        "published_at": str(input_data.get("published_at") or ""),
        "checkpoint": checkpoint,
        "checkpoint_hours": CHECKPOINT_HOURS[checkpoint],
        "observed_at": observed_at,
        "metrics": metrics,
        "data_status": data_status,
        "metrics_source": source,
        "experiment": input_data.get("experiment") or {},
    }
    return {
        "status": "success" if data_status != "unavailable" else "degraded",
        "generated_at": now_iso(),
        "snapshot": snapshot,
        "errors": errors,
    }


def run(job_dir: Path) -> int:
    try:
        input_data = json.loads((job_dir / "input.json").read_text(encoding="utf-8-sig"))
        result = generate_result(input_data)
        (job_dir / OUTPUT_NAME).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (job_dir / "logs.txt").write_text(
            f"[{result['status']}] checkpoint={result['snapshot']['checkpoint']} "
            f"data_status={result['snapshot']['data_status']}\n",
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        (job_dir / "error.json").write_text(
            json.dumps({"status": "error", "generated_at": now_iso(), "error": str(exc)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    args = parser.parse_args()
    raise SystemExit(run(Path(args.job_dir).resolve()))


if __name__ == "__main__":
    main()
