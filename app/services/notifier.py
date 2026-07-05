from typing import Any

import httpx

from app.config import Settings


class FeishuNotifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self.sent_messages: list[dict[str, Any]] = []

    async def send_card(self, chat_id: str, card: dict[str, Any]) -> dict[str, Any]:
        if not chat_id:
            raise ValueError("chat_id is required")
        payload = {"receive_id": chat_id, "msg_type": "interactive", "content": card}
        self.sent_messages.append(payload)
        if not self.settings.feishu_app_id or not self.settings.feishu_app_secret:
            return {"status": "dry_run", "payload": payload}
        return {"status": "queued", "payload": payload}

    async def notify_admins(self, text: str) -> list[dict[str, Any]]:
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
        }
        chat_id = self.settings.feishu_default_chat_id
        if chat_id:
            return [await self.send_card(chat_id, card)]
        return [{"status": "dry_run", "payload": card, "reason": "FEISHU_DEFAULT_CHAT_ID not configured"}]

