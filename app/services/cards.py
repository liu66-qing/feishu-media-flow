from app.models import ContentItem


def build_review_card(items: list[ContentItem]) -> dict:
    elements = []
    for item in items:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{item.topic}**\n平台：{item.platform}  状态：{item.status}",
                },
            }
        )
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "全部通过"},
                    "type": "primary",
                    "value": {"action": "approve_all", "content_ids": [item.content_id for item in items]},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "打回修改"},
                    "type": "default",
                    "value": {"action": "reject_all", "content_ids": [item.content_id for item in items]},
                },
            ],
        }
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "blue", "title": {"tag": "plain_text", "content": "内容待审批"}},
        "elements": elements,
    }


def build_status_card(title: str, message: str, template: str = "blue") -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": template, "title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": message}}],
    }

