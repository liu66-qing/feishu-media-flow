import json as _json

from app.models import ContentItem


def build_review_card(items: list[ContentItem]) -> dict:
    elements = []
    for item in items:
        title = ""
        body = ""
        hashtags = ""
        cover = ""
        if item.payload and isinstance(item.payload, dict):
            gen = item.payload.get("generation", {})
            if isinstance(gen, dict):
                title = gen.get("selected_title", "") or ""
                body = gen.get("body", "") or ""
                tags = gen.get("hashtags", [])
                hashtags = " ".join(tags) if isinstance(tags, list) else ""
                cover = gen.get("cover_text", "") or ""

        content_parts = [f"**选题：{item.topic}**"]
        if title:
            content_parts.append(f"**标题：**{title}")
        if body:
            preview = body[:300] + ("..." if len(body) > 300 else "")
            content_parts.append(f"**正文预览：**\n{preview}")
        if hashtags:
            content_parts.append(f"**标签：**{hashtags}")
        if cover:
            content_parts.append(f"**封面文案：**{cover}")

        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(content_parts)}}
        )
        elements.append({"tag": "hr"})

    content_ids = [item.content_id for item in items]
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "通过发布"},
                    "type": "primary",
                    "value": {"action": "approve_all", "content_ids": _json.dumps(content_ids)},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "打回修改"},
                    "type": "danger",
                    "value": {"action": "reject_all", "content_ids": _json.dumps(content_ids)},
                },
            ],
        }
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "orange", "title": {"tag": "plain_text", "content": "📝 内容待审批"}},
        "elements": elements,
    }


def build_status_card(title: str, message: str, template: str = "blue") -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": template, "title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": message}}],
    }


def build_schedule_card(items: list[dict]) -> dict:
    """Build a card showing the publish schedule from bitable records."""
    elements = []
    if not items:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "当前没有排期内容"}})
    else:
        rows = []
        for item in items:
            topic = item.get("topic", "未知")
            platform = item.get("platform", "")
            scheduled_at = item.get("scheduled_at", "待定")
            status = item.get("status", "")
            rows.append(f"| {platform} | {topic} | {scheduled_at} | {status} |")
        table = "| 平台 | 选题 | 排期时间 | 状态 |\n|---|---|---|---|\n" + "\n".join(rows)
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": table}})

    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "green", "title": {"tag": "plain_text", "content": "📅 发布排期表"}},
        "elements": elements,
    }

