from typing import Any

import httpx

from app.config import Settings


class FeishuConfigError(RuntimeError):
    pass


class BitableClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self._tenant_token: str | None = None

    async def list_records(self, table_key: str) -> list[dict[str, Any]]:
        table_id = self._table_id(table_key)
        response = await self._request("GET", f"/bitable/v1/apps/{self.settings.feishu_bitable_app_token}/tables/{table_id}/records")
        return response.get("data", {}).get("items", [])

    async def create_record(self, table_key: str, fields: dict[str, Any]) -> dict[str, Any]:
        table_id = self._table_id(table_key)
        return await self._request(
            "POST",
            f"/bitable/v1/apps/{self.settings.feishu_bitable_app_token}/tables/{table_id}/records",
            json={"fields": fields},
        )

    async def update_record(self, table_key: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        table_id = self._table_id(table_key)
        return await self._request(
            "PUT",
            f"/bitable/v1/apps/{self.settings.feishu_bitable_app_token}/tables/{table_id}/records/{record_id}",
            json={"fields": fields},
        )

    async def list_fields(self, table_key: str) -> list[dict[str, Any]]:
        """Return table field definitions for read-only deployment diagnostics."""
        table_id = self._table_id(table_key)
        response = await self._request(
            "GET",
            f"/bitable/v1/apps/{self.settings.feishu_bitable_app_token}/tables/{table_id}/fields?page_size=100",
        )
        return response.get("data", {}).get("items", [])

    def validate_schema_config(self) -> dict[str, bool]:
        return {
            "app_token": bool(self.settings.feishu_bitable_app_token),
            "content": bool(self.settings.feishu_table_content),
            "materials": bool(self.settings.feishu_table_materials),
            "accounts": bool(self.settings.feishu_table_accounts),
            "publish_logs": bool(self.settings.feishu_table_publish_logs),
            "config": bool(self.settings.feishu_table_config),
        }

    def _table_id(self, table_key: str) -> str:
        value = getattr(self.settings, f"feishu_table_{table_key}", "")
        if not value:
            raise FeishuConfigError(f"Missing FEISHU_TABLE_{table_key.upper()} configuration")
        if not self.settings.feishu_bitable_app_token:
            raise FeishuConfigError("Missing FEISHU_BITABLE_APP_TOKEN configuration")
        return value

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = await self._tenant_access_token()
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://open.feishu.cn/open-apis", timeout=20)
        try:
            response = await client.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
            response.raise_for_status()
            data = response.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Feishu API error: {data}")
            return data
        finally:
            if close_client:
                await client.aclose()

    async def _tenant_access_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        if not self.settings.feishu_app_id or not self.settings.feishu_app_secret:
            raise FeishuConfigError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET configuration")
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url="https://open.feishu.cn/open-apis", timeout=20)
        try:
            response = await client.post(
                "/auth/v3/tenant_access_token/internal",
                json={"app_id": self.settings.feishu_app_id, "app_secret": self.settings.feishu_app_secret},
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Feishu token error: {data}")
            self._tenant_token = data["tenant_access_token"]
            return self._tenant_token
        finally:
            if close_client:
                await client.aclose()
