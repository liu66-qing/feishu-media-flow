import json
from pathlib import Path

import pytest

from app.config import Settings
from app.models import CriticFeedback, CriticScore, DraftStatus, Platform
from app.services.agent_loop import AgentLoop
from app.services.publisher import PublishResult


class FakeBitable:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def list_records(self, table_key: str) -> list[dict]:
        if table_key == "accounts":
            return []
        return self.records

    async def create_record(self, table_key: str, fields: dict) -> dict:
        record = {"record_id": f"rec-{len(self.records) + 1}", "fields": dict(fields)}
        self.records.append(record)
        return {"data": {"record": record}}

    async def update_record(self, table_key: str, record_id: str, fields: dict) -> dict:
        record = next(item for item in self.records if item["record_id"] == record_id)
        record["fields"].update(fields)
        return {"data": {"record": record}}


class FakeNotifier:
    def __init__(self) -> None:
        self.cards: list[tuple[str, dict]] = []
        self.messages: list[str] = []

    async def upload_image(self, image_path: str | Path) -> str:
        return f"img-{Path(image_path).stem}"

    async def send_card(self, chat_id: str, card: dict) -> dict:
        self.cards.append((chat_id, card))
        return {"status": "ok"}

    async def notify_admins(self, text: str) -> list[dict]:
        self.messages.append(text)
        return [{"status": "ok"}]


class PassingCritic:
    async def evaluate(self, draft) -> CriticFeedback:
        return CriticFeedback(
            decision="pass",
            scores=CriticScore(
                hook=4,
                information_density=4,
                naturalness=4,
                platform_fit=4,
                actionability=4,
            ),
        )


class FakeRunner:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.calls: list[str] = []

    def run(self, skill_name: str, job) -> dict:
        self.calls.append(skill_name)
        if skill_name == "content-generate-xhs":
            return {
                "content_id": job.content_id,
                "selected_title": "社团招新实战清单",
                "body": "这是一篇用于状态机测试的完整小红书正文。",
                "hashtags": ["#社团招新", "#校园运营", "#小红书运营"],
                "cover_text": "招新实战清单",
            }
        if skill_name == "image-compose":
            image_path = self.tmp_path / "cover.png"
            image_path.write_bytes(b"png")
            return {"status": "success", "data": {"image_path": str(image_path)}}
        if skill_name == "xhs-publish-package":
            package_dir = self.tmp_path / "publish_package"
            assets_dir = package_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            asset_path = assets_dir / "cover.png"
            asset_path.write_bytes(b"png")
            return {
                "status": "success",
                "data": {"publish_package_path": str(package_dir), "files_count": 6},
            }
        raise AssertionError(f"unexpected skill: {skill_name}")


class FakePublisher:
    def __init__(self) -> None:
        self.payloads = []

    def publish(self, payload) -> PublishResult:
        self.payloads.append(payload)
        return PublishResult(success=True, platform=payload.platform, message="Published")


def find_content(store: FakeBitable, content_id: str) -> dict:
    return next(record for record in store.records if record["fields"].get("content_id") == content_id)


@pytest.mark.asyncio
async def test_xhs_command_runs_to_card_then_approval_runs_to_publish(tmp_path) -> None:
    store = FakeBitable()
    notifier = FakeNotifier()
    runner = FakeRunner(tmp_path)
    publisher = FakePublisher()
    agent = AgentLoop(
        Settings(data_dir=tmp_path, feishu_default_chat_id="chat-default"),
        bitable=store,
        notifier=notifier,
        critic=PassingCritic(),
        runner=runner,
        publisher=publisher,
    )

    created = await agent.create_content_from_topic(Platform.XHS, "社团招新", chat_id="chat-source")
    content_id = created["content_id"]
    record = find_content(store, content_id)

    assert record["fields"]["status"] == DraftStatus.AWAITING_PUBLISH_APPROVAL.value
    assert runner.calls == ["content-generate-xhs", "image-compose", "xhs-publish-package"]
    assert notifier.cards[0][0] == "chat-source"
    card = notifier.cards[0][1]
    assert any(element.get("tag") == "img" for element in card["elements"])
    approve_button = next(
        action
        for element in card["elements"]
        if element.get("tag") == "action"
        for action in element["actions"]
        if action["value"]["action"] == "approve_publish"
    )
    assert approve_button["value"]["content_id"] == content_id

    approved = await agent.approve_publish(content_id, "ou-reviewer")
    assert approved["next_state"] == DraftStatus.PUBLISH_APPROVED.value
    await agent.run_until_checkpoint(content_id)

    assert record["fields"]["status"] == DraftStatus.PUBLISHED.value
    assert record["fields"]["reviewed_by"] == "ou-reviewer"
    assert publisher.payloads[0].platform == Platform.XHS.value
    assert publisher.payloads[0].account == "default"
    assert publisher.payloads[0].image_paths == [str(tmp_path / "publish_package" / "assets" / "cover.png")]


@pytest.mark.asyncio
async def test_approval_requires_the_matching_checkpoint(tmp_path) -> None:
    store = FakeBitable()
    await store.create_record(
        "content",
        {"content_id": "CNT-1", "status": DraftStatus.GENERATING.value},
    )
    agent = AgentLoop(
        Settings(data_dir=tmp_path),
        bitable=store,
        notifier=FakeNotifier(),
        critic=PassingCritic(),
        runner=FakeRunner(tmp_path),
        publisher=FakePublisher(),
    )

    result = await agent.approve_publish("CNT-1", "ou-reviewer")

    assert result == {"status": "invalid_state", "id": "CNT-1", "current_state": "generating"}
    assert find_content(store, "CNT-1")["fields"]["status"] == DraftStatus.GENERATING.value


@pytest.mark.asyncio
async def test_legacy_card_action_is_explicitly_deprecated(tmp_path) -> None:
    agent = AgentLoop(
        Settings(data_dir=tmp_path),
        bitable=FakeBitable(),
        notifier=FakeNotifier(),
        critic=PassingCritic(),
        runner=FakeRunner(tmp_path),
        publisher=FakePublisher(),
    )

    result = await agent.handle_card_action({"action": "approve_all", "content_ids": json.dumps(["CNT-1"])})

    assert result["status"] == "deprecated_action"
