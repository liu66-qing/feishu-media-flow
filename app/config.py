from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_base_url: str = "http://127.0.0.1:8000"
    data_dir: Path = Path(".data")

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_webhook_secret: str = ""
    feishu_admin_open_ids: str = ""
    feishu_default_chat_id: str = ""

    feishu_bitable_app_token: str = ""
    feishu_table_content: str = ""
    feishu_table_materials: str = ""
    feishu_table_accounts: str = ""
    feishu_table_publish_logs: str = ""
    feishu_table_config: str = ""

    skill_root: Path = Path("skills/media-workflow/scripts")
    skill_timeout_seconds: int = Field(default=120, ge=1)

    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    @property
    def admin_open_ids(self) -> list[str]:
        return [item.strip() for item in self.feishu_admin_open_ids.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings

