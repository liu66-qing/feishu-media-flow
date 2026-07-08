from app.models import ContentItem


def build_review_card(items: list[ContentItem]) -> dict:
    elements = []
    for item in items:
        body_preview = ""
        if item.payload and isinstance(item.payload, dict):
            gen = item.payload.get("generation", {})
            if isinstance(gen, dict):
                data = gen.get("data", gen)
                body_preview = str(data.get("body", "") or data.get("topic", ""))[:200]

        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{item.topic}**\n"
                        f"平台：{item.platform.value if hasattr(item.platform, 'value') else item.platform}\n"
                        f"状态：{item.status.value if hasattr(item.status, 'value') else item.status}"
                        + (f"\n\n> {body_preview}..." if body_preview else "")
                    ),
                },
            }
        )
    content_ids = [item.content_id for item in items]
    import json as _json
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "通过"},
                    "type": "primary",
                    "value": {"action": "approve_all", "content_ids": _json.dumps(content_ids)},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "拒绝"},
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

