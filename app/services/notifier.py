import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuNotifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._tenant_token: str | None = None

    async def _get_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        async with httpx.AsyncClient(base_url=FEISHU_BASE, timeout=10) as c:
            resp = await c.post(
                "/auth/v3/tenant_access_token/internal",
                json={"app_id": self.settings.feishu_app_id, "app_secret": self.settings.feishu_app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"token error: {data}")
            self._tenant_token = data["tenant_access_token"]
            return self._tenant_token

    async def _api(self, method: str, path: str, body: dict | None = None) -> dict:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(base_url=FEISHU_BASE, timeout=15) as c:
            resp = await c.request(method, path, headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()

    async def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }
        try:
            result = await self._api("POST", "/im/v1/messages?receive_id_type=chat_id", body)
            logger.info("sent text to %s", chat_id)
            return result
        except Exception as e:
            logger.error("send_text failed: %s", e)
            return {"status": "error", "detail": str(e)}

    async def send_card(self, chat_id: str, card: dict[str, Any]) -> dict[str, Any]:
        if not chat_id:
            raise ValueError("chat_id is required")
        body = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
        }
        try:
            result = await self._api("POST", "/im/v1/messages?receive_id_type=chat_id", body)
            logger.info("sent card to %s", chat_id)
            return result
        except Exception as e:
            logger.error("send_card failed: %s", e)
            return {"status": "error", "detail": str(e)}

    async def reply_text(self, message_id: str, text: str) -> dict[str, Any]:
        body = {
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }
        try:
            result = await self._api("POST", f"/im/v1/messages/{message_id}/reply", body)
            logger.info("replied to %s", message_id)
            return result
        except Exception as e:
            logger.error("reply_text failed: %s", e)
            return {"status": "error", "detail": str(e)}

    async def upload_image(self, image_path: str | Path) -> str | None:
        """Upload image to Feishu and return image_key."""
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        path = Path(image_path)
        if not path.exists():
            logger.error("image not found: %s", path)
            return None
        try:
            async with httpx.AsyncClient(base_url=FEISHU_BASE, timeout=30) as c:
                resp = await c.post(
                    "/im/v1/images",
                    headers=headers,
                    data={"image_type": "message"},
                    files={"image": (path.name, path.read_bytes(), "image/png")},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 0:
                    image_key = data["data"]["image_key"]
                    logger.info("uploaded image: %s -> %s", path.name, image_key)
                    return image_key
                logger.error("upload_image failed: %s", data)
                return None
        except Exception as e:
            logger.error("upload_image error: %s", e)
            return None

    async def send_image(self, chat_id: str, image_key: str) -> dict[str, Any]:
        """Send image message to chat."""
        body = {
            "receive_id": chat_id,
            "msg_type": "image",
            "content": json.dumps({"image_key": image_key}),
        }
        try:
            result = await self._api("POST", "/im/v1/messages?receive_id_type=chat_id", body)
            logger.info("sent image to %s", chat_id)
            return result
        except Exception as e:
            logger.error("send_image failed: %s", e)
            return {"status": "error", "detail": str(e)}

    async def send_image_card(self, chat_id: str, image_key: str, title: str, content_id: str) -> dict[str, Any]:
        """Send a rich card with embedded image and approve/reject buttons."""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "green", "title": {"tag": "plain_text", "content": f"🎨 封面图待确认：{title}"}},
            "elements": [
                {"tag": "img", "img_key": image_key, "alt": {"tag": "plain_text", "content": title}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**内容ID：**{content_id}"}},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "确认发布"},
                            "type": "primary",
                            "value": {"action": "confirm_publish", "content_ids": json.dumps([content_id])},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "重新生成"},
                            "type": "danger",
                            "value": {"action": "regenerate_image", "content_ids": json.dumps([content_id])},
                        },
                    ],
                },
            ],
        }
        return await self.send_card(chat_id, card)

    async def notify_admins(self, text: str) -> list[dict[str, Any]]:
        chat_id = self.settings.feishu_default_chat_id
        if not chat_id:
            return [{"status": "skipped", "reason": "no default chat_id"}]
        return [await self.send_text(chat_id, text)]
