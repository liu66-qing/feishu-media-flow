import html
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings


class WechatConfigError(RuntimeError):
    pass


def markdown_to_wechat_html(markdown: str, inline_images: list[dict[str, str]] | None = None) -> str:
    """Render the supported Markdown subset and insert images after target headings."""
    lines = []
    pending_images = [dict(item) for item in (inline_images or []) if item.get("url")]

    def append_heading_images(heading: str) -> None:
        normalized_heading = heading.strip().lstrip("#").strip()
        remaining = []
        for item in pending_images:
            target = str(item.get("target_heading") or "").strip().lstrip("#").strip()
            if target and (
                target == normalized_heading
                or target in normalized_heading
                or normalized_heading in target
            ):
                url = html.escape(str(item["url"]), quote=True)
                alt = html.escape(str(item.get("alt_text") or normalized_heading), quote=True)
                lines.append(
                    f'<img src="{url}" alt="{alt}" '
                    'style="display:block;width:100%;height:auto;margin:18px auto;" />'
                )
            else:
                remaining.append(item)
        pending_images[:] = remaining

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            heading = line[4:]
            lines.append(f"<h3>{html.escape(heading)}</h3>")
            append_heading_images(heading)
        elif line.startswith("## "):
            heading = line[3:]
            lines.append(f"<h2>{html.escape(heading)}</h2>")
            append_heading_images(heading)
        elif line.startswith("# "):
            heading = line[2:]
            lines.append(f"<h1>{html.escape(heading)}</h1>")
            append_heading_images(heading)
        elif line.startswith("- "):
            lines.append(f"<p>• {html.escape(line[2:])}</p>")
        elif re.match(r"^\d+\.\s+", line):
            lines.append(f"<p>{html.escape(line)}</p>")
        elif match := re.fullmatch(r"!\[([^]]*)\]\((https?://[^)]+)\)", line):
            alt, url = match.groups()
            lines.append(
                f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt, quote=True)}" '
                'style="display:block;width:100%;height:auto;margin:18px auto;" />'
            )
        else:
            lines.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(lines)


@dataclass
class WechatDraft:
    title: str
    author: str
    digest: str
    content_markdown: str
    thumb_media_id: str
    inline_images: list[dict[str, str]] = field(default_factory=list)


class WechatDraftClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._access_token: str | None = None

    async def create_draft(self, draft: WechatDraft) -> dict[str, Any]:
        token = await self._token()
        article_html = markdown_to_wechat_html(draft.content_markdown, draft.inline_images)
        missing_targets = [
            str(item.get("target_heading") or "未标注小节")
            for item in draft.inline_images
            if item.get("url") and html.escape(str(item["url"]), quote=True) not in article_html
        ]
        if missing_targets:
            raise RuntimeError(
                "WeChat inline image target heading not found: " + ", ".join(missing_targets)
            )
        payload = {
            "articles": [
                {
                    "title": draft.title[:64],
                    "author": draft.author,
                    "digest": draft.digest,
                    "content": article_html,
                    "thumb_media_id": draft.thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://api.weixin.qq.com", timeout=20)
        try:
            response = await client.post(f"/cgi-bin/draft/add?access_token={token}", json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("errcode", 0) != 0:
                raise RuntimeError(f"WeChat draft error: {data}")
            return data
        finally:
            if close_client:
                await client.aclose()

    async def upload_cover(self, image_path: str | Path) -> str:
        """Upload a permanent image material and return its media_id for draft cover use."""
        token = await self._token()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"WeChat cover image not found: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://api.weixin.qq.com", timeout=30)
        try:
            response = await client.post(
                f"/cgi-bin/material/add_material?access_token={token}&type=image",
                files={"media": (path.name, path.read_bytes(), mime_type)},
            )
            response.raise_for_status()
            data = response.json()
            media_id = data.get("media_id")
            if not media_id:
                raise RuntimeError(f"WeChat cover upload error: {data}")
            return str(media_id)
        finally:
            if close_client:
                await client.aclose()

    async def upload_inline_image(self, image_path: str | Path) -> str:
        """Upload an article image and return the URL accepted by draft content HTML."""
        token = await self._token()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"WeChat inline image not found: {path}")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://api.weixin.qq.com", timeout=30)
        try:
            response = await client.post(
                f"/cgi-bin/media/uploadimg?access_token={token}",
                files={"media": (path.name, path.read_bytes(), mime_type)},
            )
            response.raise_for_status()
            data = response.json()
            url = data.get("url")
            if not url:
                raise RuntimeError(f"WeChat inline image upload error: {data}")
            return str(url)
        finally:
            if close_client:
                await client.aclose()

    async def _token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatConfigError("Missing WECHAT_APP_ID or WECHAT_APP_SECRET configuration")
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://api.weixin.qq.com", timeout=20)
        try:
            response = await client.get(
                "/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            if "access_token" not in data:
                raise RuntimeError(f"WeChat token error: {data}")
            self._access_token = data["access_token"]
            return self._access_token
        finally:
            if close_client:
                await client.aclose()
