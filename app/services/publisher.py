"""Publisher adapter — wraps social-auto-upload CLI for multi-platform publishing.

Supports: xiaohongshu, douyin, kuaishou, bilibili, tencent (video channels).
WeChat Official Account uses separate API (not browser automation).
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
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
        return PublishResult(
            success=result.returncode == 0,
            platform="xiaohongshu",
            message="Published" if result.returncode == 0 else result.stderr[-500:],
            stdout=result.stdout,
            stderr=result.stderr,
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
