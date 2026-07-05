from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


class WechatConfigError(RuntimeError):
    pass


def markdown_to_wechat_html(markdown: str) -> str:
    lines = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            lines.append(f"<p>• {line[2:]}</p>")
        else:
            lines.append(f"<p>{line}</p>")
    return "\n".join(lines)


@dataclass
class WechatDraft:
    title: str
    author: str
    digest: str
    content_markdown: str
    thumb_media_id: str


class WechatDraftClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._access_token: str | None = None

    async def create_draft(self, draft: WechatDraft) -> dict[str, Any]:
        token = await self._token()
        html = markdown_to_wechat_html(draft.content_markdown)
        payload = {
            "articles": [
                {
                    "title": draft.title,
                    "author": draft.author,
                    "digest": draft.digest,
                    "content": html,
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

