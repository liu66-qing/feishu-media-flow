import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests


SKILL_DIR = Path(__file__).resolve().parent
VIDEO_API_URL = os.getenv("VIDEO_API_URL", "http://localhost:8080")
POLL_INTERVAL = 5
TIMEOUT_SECONDS = 600


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def submit_video_task(input_data: Dict[str, Any]) -> str:
    url = f"{VIDEO_API_URL}/api/video/generate"
    payload = {
        "topic": input_data.get("topic", ""),
        "voice_name": input_data.get("voice_name", "zh-CN-YunxiNeural"),
        "video_source": input_data.get("video_source", "pexels"),
        "duration": int(input_data.get("duration", 60)),
        "language": "zh"
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result.get("task_id")


def poll_task_status(task_id: str) -> Dict[str, Any]:
    url = f"{VIDEO_API_URL}/api/video/status/{task_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def download_file(url: str, dest_path: Path) -> None:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def generate_video(input_data: Dict[str, Any], job_dir: Path) -> Dict[str, Any]:
    task_id = submit_video_task(input_data)
    if not task_id:
        raise RuntimeError("Failed to get task_id from video API")

    start_time = time.time()
    while time.time() - start_time < TIMEOUT_SECONDS:
        status = poll_task_status(task_id)
        task_status = status.get("status", "")

        if task_status == "completed":
            output_dir = job_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            video_url = status.get("video_url")
            cover_url = status.get("cover_url")
            subtitle_url = status.get("subtitle_url")

            video_path = output_dir / "video.mp4"
            cover_path = output_dir / "cover.jpg"
            subtitle_path = output_dir / "subtitles.srt"

            if video_url:
                download_file(video_url, video_path)
            if cover_url:
                download_file(cover_url, cover_path)
            if subtitle_url:
                download_file(subtitle_url, subtitle_path)

            return {
                "content_id": input_data.get("content_id", ""),
                "job_id": input_data.get("job_id", ""),
                "video_path": str(video_path),
                "cover_path": str(cover_path),
                "duration": status.get("duration", 0),
                "script": status.get("script", ""),
                "subtitle_path": str(subtitle_path)
            }

        if task_status == "failed":
            raise RuntimeError(status.get("error", "Video generation failed"))

        time.sleep(POLL_INTERVAL)

    raise RuntimeError(f"Video generation timeout after {TIMEOUT_SECONDS} seconds")


def run(job_dir: str) -> int:
    job_dir_path = Path(job_dir)
    input_path = job_dir_path / "input.json"
    output_path = job_dir_path / "video-generate.json"
    logs_path = job_dir_path / "logs.txt"
    error_path = job_dir_path / "error.json"

    try:
        input_data = load_json(input_path)
        result = generate_video(input_data, job_dir_path)
        write_json(output_path, result)

        logs_path.write_text(
            f"[success] video-generate finished. duration={result.get('duration', 0)}\n",
            encoding="utf-8"
        )
        return 0
    except Exception as e:
        write_json(error_path, {
            "status": "error",
            "generated_at": utc_now(),
            "error": str(e)
        })
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Path to job directory containing input.json")
    args = parser.parse_args()

    exit_code = run(args.job_dir)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()