import json

from app.config import Settings
from app.models import DraftStatus
from app.services.agent_loop import AgentLoop
from app.services.media_delivery import MediaDeliveryService


class FakeBitable:
    def __init__(self) -> None:
        self.updated = []

    async def update_record(self, table_key: str, record_id: str, fields: dict) -> dict:
        self.updated.append((table_key, record_id, fields))
        return {"ok": True}


class FakeNotifier:
    def __init__(self) -> None:
        self.cards = []
        self.texts = []

    async def upload_image(self, image_path: str) -> str:
        return f"key-{image_path.split('/')[-1]}"

    async def send_card(self, chat_id: str, card: dict) -> dict:
        self.cards.append((chat_id, card))
        return {"ok": True}

    async def notify_admins(self, text: str) -> list[dict]:
        self.texts.append(text)
        return [{"ok": True}]


class FakeRunner:
    def __init__(self) -> None:
        self.jobs = []

    def run(self, skill_name: str, job) -> dict:
        self.jobs.append((skill_name, job))
        if skill_name == "video-generate":
            return {
                "status": "success",
                "card_paths": ["/tmp/card_01.png", "/tmp/card_02.png", "/tmp/card_03.png"],
                "caption": job.body,
                "hashtags": job.hashtags,
            }
        if skill_name == "image-compose":
            return {
                "status": "success",
                "data": {"image_path": f"/tmp/{job.job_id}.png"},
            }
        raise AssertionError(f"unexpected skill: {skill_name}")


def test_wechat_fallback_plan_contains_cover_and_two_inline_images() -> None:
    plan = MediaDeliveryService._normalize_wechat_image_plan(
        {
            "sections": [
                {"heading": "引言"},
                {"heading": "背景现状"},
                {"heading": "关键观察"},
            ]
        },
        "校园活动复盘",
    )
    assert [item["role"] for item in plan] == ["cover", "inline", "inline"]
    assert [item["target_heading"] for item in plan[1:]] == ["背景现状", "关键观察"]


async def test_agent_delivers_douyin_cards_without_publish_action(tmp_path) -> None:
    bitable = FakeBitable()
    notifier = FakeNotifier()
    runner = FakeRunner()
    agent = AgentLoop(
        Settings(data_dir=tmp_path, feishu_default_chat_id="chat-default"),
        bitable=bitable,
        notifier=notifier,
        runner=runner,
    )
    record = {
        "record_id": "rec-douyin",
        "fields": {
            "content_id": "CNT-DY-1",
            "platform": "douyin",
            "chat_id": "chat-request",
            "content_payload": json.dumps(
                {
                    "selected_title": "招新现场别只会发传单",
                    "body": "按顺序上传这组图文卡片。",
                    "hashtags": ["#社团招新"],
                    "cover_lines": ["招新现场", "别只会发传单"],
                    "cards": [
                        {"title": "问题", "body": "正文", "kind": "detail"},
                        {"title": "总结", "body": "总结", "kind": "summary"},
                    ],
                },
                ensure_ascii=False,
            ),
        },
    }

    result = await agent._handle_passed(record)

    assert result == {"action": "douyin_cards_delivered", "card_count": 3}
    assert bitable.updated[-1][2]["status"] == DraftStatus.AWAITING_PUBLISH_APPROVAL.value
    image_result = json.loads(bitable.updated[-1][2]["image_result"])
    assert image_result["delivery_mode"] == "manual_upload"
    assert runner.jobs[0][0] == "video-generate"
    assert runner.jobs[0][1].output_size == {"width": 1080, "height": 1350}
    assert runner.jobs[0][1].variables["visual_style"] == "auto"
    serialized_card = str(notifier.cards[-1][1])
    assert "手动上传" in serialized_card
    assert "approve_publish" not in serialized_card


async def test_xhs_image_compose_uses_topic_driven_template_selection(tmp_path) -> None:
    bitable = FakeBitable()
    runner = FakeRunner()
    agent = AgentLoop(
        Settings(data_dir=tmp_path),
        bitable=bitable,
        notifier=FakeNotifier(),
        runner=runner,
    )
    record = {
        "record_id": "rec-xhs",
        "fields": {
            "content_id": "CNT-XHS-1",
            "content_payload": json.dumps(
                {
                    "selected_title": "AI 展到底怎么看？",
                    "cover_text": "逛 AI 展先问这三件事",
                },
                ensure_ascii=False,
            ),
        },
    }

    await agent._compose_image(record)

    skill_name, job = runner.jobs[0]
    assert skill_name == "image-compose"
    assert job.template_name == ""
    assert job.variables["visual_style"] == "auto"
    assert job.variables["template_role"] == "cover"


async def test_douyin_never_enters_automatic_publisher(tmp_path) -> None:
    bitable = FakeBitable()
    agent = AgentLoop(
        Settings(data_dir=tmp_path),
        bitable=bitable,
        notifier=FakeNotifier(),
        runner=FakeRunner(),
    )
    record = {
        "record_id": "rec-douyin-scheduled",
        "fields": {"content_id": "CNT-DY-2", "platform": "douyin", "status": "scheduled"},
    }

    result = await agent._handle_scheduled(record)

    assert result == {"action": "manual_delivery_only", "platform": "douyin"}
    assert bitable.updated[-1][2]["status"] == DraftStatus.AWAITING_PUBLISH_APPROVAL.value
    assert set(bitable.updated[-1][2]) == {"status"}


async def test_agent_delivers_wechat_article_and_labeled_images(tmp_path) -> None:
    bitable = FakeBitable()
    notifier = FakeNotifier()
    runner = FakeRunner()
    agent = AgentLoop(
        Settings(data_dir=tmp_path, feishu_default_chat_id="chat-default"),
        bitable=bitable,
        notifier=notifier,
        runner=runner,
    )
    record = {
        "record_id": "rec-wechat",
        "fields": {
            "content_id": "CNT-WX-1",
            "platform": "wechat",
            "chat_id": "chat-request",
            "content_payload": json.dumps(
                {
                    "selected_title": "校园活动复盘方法",
                    "summary": "一篇讲清校园活动复盘的文章。",
                    "body_md": "# 校园活动复盘方法\n\n## 背景现状\n正文\n\n## 关键变化\n正文",
                    "sections": [{"heading": "背景现状"}, {"heading": "关键变化"}],
                    "image_plan": [
                        {"role": "cover", "title": "校园活动复盘", "prompt": "校园活动复盘"},
                        {
                            "role": "inline",
                            "title": "背景现状",
                            "prompt": "大学校园活动现场",
                            "target_heading": "背景现状",
                            "alt_text": "活动背景",
                        },
                        {
                            "role": "inline",
                            "title": "关键变化",
                            "prompt": "大学生复盘讨论",
                            "target_heading": "关键变化",
                            "alt_text": "关键变化",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
        },
    }

    result = await agent._handle_passed(record)

    assert result["action"] == "wechat_article_delivered"
    assert result["image_count"] == 3
    assert result["draft_created"] is False
    image_result = json.loads(bitable.updated[-1][2]["image_result"])
    assert image_result["delivery_mode"] == "manual_insert"
    assert len(notifier.cards) == 2
    delivery_card = str(notifier.cards[-1][1])
    assert "封面图" in delivery_card
    assert "插在「背景现状」小节标题之后" in delivery_card
    assert "插在「关键变化」小节标题之后" in delivery_card
