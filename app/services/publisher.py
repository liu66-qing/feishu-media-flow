"""Publisher adapter — wraps social-auto-upload CLI for multi-platform publishing.

Supports: xiaohongshu, douyin, kuaishou, bilibili, tencent (video channels).
WeChat Official Account uses separate API (not browser automation).
"""

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

SAU_CLI = "sau_cli.py"


@dataclass
class PublishPayload:
    platform: str
    account: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    video_path: str = ""
    schedule: str = ""  # format: %Y-%m-%d %H:%M


@dataclass
class PublishResult:
    success: bool
    platform: str
    message: str = ""
    stdout: str = ""
    stderr: str = ""
    post_id: str = ""
    post_url: str = ""
    published_at: str = ""


class Publisher:
    """Adapter over social-auto-upload CLI."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.sau_dir = Path(settings.skill_root) / "vendor" / "social-auto-upload"
        self.python = sys.executable

    def _run_sau(self, args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
        cmd = [self.python, SAU_CLI] + args
        logger.info("sau cmd: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            cwd=str(self.sau_dir),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish content to target platform via sau CLI."""
        dispatch = {
            "xhs": self._publish_xhs_note,
            "xiaohongshu": self._publish_xhs_note,
            "douyin": self._publish_douyin,
            "kuaishou": self._publish_kuaishou,
            "bilibili": self._publish_bilibili,
            "tencent": self._publish_tencent,
        }

        handler = dispatch.get(payload.platform)
        if not handler:
            return PublishResult(
                success=False,
                platform=payload.platform,
                message=f"Unsupported platform: {payload.platform}",
            )

        try:
            return handler(payload)
        except subprocess.TimeoutExpired:
            return PublishResult(
                success=False, platform=payload.platform, message="Publish timed out"
            )
        except Exception as e:
            return PublishResult(
                success=False, platform=payload.platform, message=str(e)
            )

    def login(self, platform: str, account: str) -> PublishResult:
        """Interactive login (requires browser, QR scan)."""
        platform_map = {
            "xhs": "xiaohongshu",
            "xiaohongshu": "xiaohongshu",
            "douyin": "douyin",
            "kuaishou": "kuaishou",
            "bilibili": "bilibili",
            "tencent": "tencent",
        }
        sau_platform = platform_map.get(platform, platform)
        result = self._run_sau([sau_platform, "login", "--account", account], timeout=300)
        return PublishResult(
            success=result.returncode == 0,
            platform=platform,
            message="Login OK" if result.returncode == 0 else "Login failed",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def check_account(self, platform: str, account: str) -> PublishResult:
        """Check if account cookie is still valid."""
        platform_map = {"xhs": "xiaohongshu", "xiaohongshu": "xiaohongshu"}
        sau_platform = platform_map.get(platform, platform)
        result = self._run_sau([sau_platform, "check", "--account", account])
        return PublishResult(
            success=result.returncode == 0,
            platform=platform,
            message="Cookie valid" if result.returncode == 0 else "Cookie expired",
            stdout=result.stdout,
            stderr=result.stderr,
        )

    # ------------------------------------------------------------------
    # Platform-specific publish methods
    # ------------------------------------------------------------------

    def _publish_xhs_note(self, payload: PublishPayload) -> PublishResult:
        args = [
            "xiaohongshu", "upload-note",
            "--account", payload.account,
            "--title", payload.title[:20],
            "--images", *payload.image_paths,
        ]
        if payload.body:
            args.extend(["--note", payload.body])
        if payload.tags:
            args.extend(["--tags", ",".join(payload.tags[:10])])
        if payload.schedule:
            args.extend(["--schedule", payload.schedule])
        args.append("--headless")

        result = self._run_sau(args)
        metadata = _extract_publish_metadata(result.stdout)
        return PublishResult(
            success=result.returncode == 0,
            platform="xiaohongshu",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
            post_id=metadata["post_id"],
            post_url=metadata["post_url"],
            published_at=metadata["published_at"] if result.returncode == 0 else "",
        )

    def _publish_douyin(self, payload: PublishPayload) -> PublishResult:
        if payload.video_path:
            args = [
                "douyin", "upload-video",
                "--account", payload.account,
                "--file", payload.video_path,
                "--title", payload.title[:30],
            ]
        else:
            args = [
                "douyin", "upload-note",
                "--account", payload.account,
                "--title", payload.title[:30],
                "--images", *payload.image_paths,
            ]
        if payload.tags:
            args.extend(["--tags", ",".join(payload.tags)])
        if payload.schedule:
            args.extend(["--schedule", payload.schedule])
        args.append("--headless")

        result = self._run_sau(args)
        return PublishResult(
            success=result.returncode == 0,
            platform="douyin",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def _publish_kuaishou(self, payload: PublishPayload) -> PublishResult:
        args = [
            "kuaishou", "upload-video" if payload.video_path else "upload-note",
            "--account", payload.account,
            "--title", payload.title,
        ]
        if payload.video_path:
            args.extend(["--file", payload.video_path])
        else:
            args.extend(["--images", *payload.image_paths])
        if payload.tags:
            args.extend(["--tags", ",".join(payload.tags)])
        args.append("--headless")

        result = self._run_sau(args)
        return PublishResult(
            success=result.returncode == 0,
            platform="kuaishou",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def _publish_bilibili(self, payload: PublishPayload) -> PublishResult:
        args = [
            "bilibili", "upload-video",
            "--account", payload.account,
            "--file", payload.video_path,
            "--title", payload.title,
        ]
        if payload.tags:
            args.extend(["--tags", ",".join(payload.tags)])
        args.append("--headless")

        result = self._run_sau(args)
        return PublishResult(
            success=result.returncode == 0,
            platform="bilibili",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def _publish_tencent(self, payload: PublishPayload) -> PublishResult:
        args = [
            "tencent", "upload-video",
            "--account", payload.account,
            "--file", payload.video_path,
            "--title", payload.title,
        ]
        if payload.tags:
            args.extend(["--tags", ",".join(payload.tags)])
        args.append("--headless")

        result = self._run_sau(args)
        return PublishResult(
            success=result.returncode == 0,
            platform="tencent",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
        )


def _extract_publish_metadata(stdout: str) -> dict[str, str]:
    """Extract a post identifier/URL from structured or human CLI output."""
    post_id = ""
    post_url = ""
    for line in reversed(str(stdout or "").splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            post_id = str(payload.get("post_id") or payload.get("note_id") or payload.get("id") or "")
            post_url = str(payload.get("post_url") or payload.get("url") or payload.get("share_url") or "")
            if post_id or post_url:
                break
    if not post_url:
        match = re.search(r"https?://[^\s\]\)\"']+", str(stdout or ""))
        post_url = match.group(0) if match else ""
    if not post_id and post_url:
        match = re.search(r"(?:explore|discovery/item|video)/(\w+)", post_url)
        post_id = match.group(1) if match else ""
    return {
        "post_id": post_id,
        "post_url": post_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
