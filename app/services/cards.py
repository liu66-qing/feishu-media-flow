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
            content_parts.append(f"**🎨 封面生图描述：**{cover}")

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
                    "text": {"tag": "plain_text", "content": "通过 + AI生图"},
                    "type": "primary",
                    "value": {"action": "approve_ai_image", "content_ids": _json.dumps(content_ids)},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "通过 + 模板图"},
                    "type": "default",
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


def build_schedule_card(items: list[dict], bitable_app_token: str = "") -> dict:
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

    if bitable_app_token:
        link = f"https://zcn1pye3srj4.feishu.cn/base/{bitable_app_token}"
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"[📊 查看完整排期表]({link})"}})

    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "green", "title": {"tag": "plain_text", "content": "📅 发布排期表"}},
        "elements": elements,
    }


_PLATFORM_LABEL = {"xhs": "小红书", "douyin": "抖音", "weibo": "微博", "wechat": "公众号"}


def build_material_review_card(topics: list[dict]) -> dict:
    """Build a weekly material review card with per-topic adopt buttons.

    Each topic dict is expected to have:
      - title: str
      - source: str  (e.g. "weibo", "xhs")
      - angle_suggestion: str
      - suggested_platform: str  (e.g. "xhs", "douyin")
    """
    elements: list[dict] = []

    for idx, topic in enumerate(topics, start=1):
        title = topic.get("title", "")
        source = topic.get("source", "")
        angle = topic.get("angle_suggestion", "")
        platform = topic.get("suggested_platform", "xhs")
        platform_label = _PLATFORM_LABEL.get(platform, platform)

        content = (
            f"**{idx}. {title}**\n"
            f"来源：{source} | 建议平台：{platform_label}\n"
            f"建议角度：{angle}"
        )
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": content}}
        )
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "采纳"},
                        "type": "primary",
                        "value": {
                            "action": "adopt_topic",
                            "topic_title": title,
                            "platform": platform,
                            "angle": angle,
                        },
                    }
                ],
            }
        )
        elements.append({"tag": "hr"})

    # Remove trailing hr
    if elements and elements[-1].get("tag") == "hr":
        elements.pop()

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "turquoise",
            "title": {"tag": "plain_text", "content": "🔥 本周热点素材"},
        },
        "elements": elements,
    }


def build_wechat_article_card(title: str, summary: str, body_md: str, hashtags: list[str] | None = None) -> dict:
    """Build a collapsible card for WeChat article content, easy to copy."""
    elements = []

    # Title and summary always visible
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**标题：**{title}"}})
    if summary:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**摘要：**{summary}"}})
    elements.append({"tag": "hr"})

    # Body in collapsible panel
    # Feishu card collapsible uses "collapsible_panel"
    body_preview = body_md[:150] + "..." if len(body_md) > 150 else body_md
    elements.append(
        {
            "tag": "collapsible_panel",
            "expanded": False,
            "header": {
                "title": {"tag": "plain_text", "content": "📄 展开查看全文（可选中复制）"},
            },
            "vertical_spacing": "8px",
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": body_md}},
            ],
        }
    )

    if hashtags:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**标签：**{' '.join(hashtags)}"}})

    elements.append({"tag": "hr"})
    elements.append(
        {"tag": "div", "text": {"tag": "lark_md", "content": "💡 展开全文后长按选中即可复制到公众号编辑器"}}
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "purple", "title": {"tag": "plain_text", "content": "📝 公众号文章已生成"}},
        "elements": elements,
    }


def build_video_review_card(
    content_id: str,
    topic: str,
    script: str,
    cover_url: str,
    video_url: str,
    duration: int,
) -> dict:
    """Build a video review card for group approval after video generation."""
    elements: list[dict] = []

    # 封面图预览
    elements.append(
        {"tag": "img", "img_key": cover_url, "alt": {"tag": "plain_text", "content": "视频封面"}}
    )
    elements.append({"tag": "hr"})

    # 基本信息
    minutes, seconds = divmod(duration, 60)
    duration_str = f"{minutes}分{seconds}秒" if minutes else f"{seconds}秒"
    info_md = f"**选题：**{topic}\n**视频时长：**{duration_str}"
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": info_md}})
    elements.append({"tag": "hr"})

    # 脚本文案（折叠面板）
    elements.append(
        {
            "tag": "collapsible_panel",
            "expanded": False,
            "header": {
                "title": {"tag": "plain_text", "content": "📜 展开查看完整脚本文案"},
            },
            "vertical_spacing": "8px",
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": script}},
            ],
        }
    )
    elements.append({"tag": "hr"})

    # 下载视频链接
    elements.append(
        {"tag": "div", "text": {"tag": "lark_md", "content": f"[📥 下载视频]({video_url})"}}
    )
    elements.append({"tag": "hr"})

    # 审批按钮
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "通过发布"},
                    "type": "primary",
                    "value": {"action": "approve_publish", "content_id": content_id},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "打回重新生成"},
                    "type": "danger",
                    "value": {"action": "reject_regenerate", "content_id": content_id},
                },
            ],
        }
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "indigo",
            "title": {"tag": "plain_text", "content": f"🎬 视频生成完成：{topic}"},
        },
        "elements": elements,
    }

