import json as _json

from app.models import ContentItem


def build_review_card(items: list[ContentItem]) -> dict:
    """Build a legacy WorkflowService card; not used by the active Feishu entrypoint."""
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
        source_url = str(topic.get("source_url", ""))
        heat_score = topic.get("heat_score", "")
        data_status = str(topic.get("data_status", "unknown"))
        material_id = str(topic.get("material_id", ""))

        content = (
            f"**{idx}. {title}**\n"
            f"来源：{source} | 建议平台：{platform_label}\n"
            f"建议角度：{angle}\n"
            f"热度：{heat_score or '未提供'} | 数据状态：{data_status}"
        )
        if source_url:
            content += f"\n[查看原始来源]({source_url})"
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
                            "material_id": material_id,
                            "source": source,
                            "source_url": source_url,
                            "heat_score": heat_score,
                            "relevance_score": topic.get("relevance_score", ""),
                            "data_status": data_status,
                            "collected_at": topic.get("collected_at", ""),
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


def build_wechat_article_card(
    title: str,
    summary: str,
    body_md: str,
    hashtags: list[str] | None = None,
    content_id: str = "",
) -> dict:
    """Build a collapsible card for WeChat article content, easy to copy."""
    elements = []

    # Title and summary always visible
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**标题：**{title}"}})
    if summary:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**摘要：**{summary}"}})
    elements.append({"tag": "hr"})

    # Body in collapsible panel
    # Feishu card collapsible uses "collapsible_panel"
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

    if content_id:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**内容 ID：**{content_id}"}}
        )

    elements.append({"tag": "hr"})
    elements.append(
        {"tag": "div", "text": {"tag": "lark_md", "content": "配图正在生成，随后会按封面和正文插入位置单独交付。"}}
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "purple", "title": {"tag": "plain_text", "content": "公众号文章已生成"}},
        "elements": elements,
    }


def build_publish_review_card(
    *,
    content_id: str,
    platform: str,
    title: str,
    body: str,
    hashtags: list[str],
    image_keys: list[str] | None = None,
) -> dict:
    """Build the single final approval card used by the AgentLoop chain."""
    platform_label = _PLATFORM_LABEL.get(platform, platform)
    elements: list[dict] = []

    for index, image_key in enumerate(image_keys or [], start=1):
        elements.append(
            {
                "tag": "img",
                "img_key": image_key,
                "alt": {"tag": "plain_text", "content": f"发布图片 {index}"},
            }
        )

    elements.extend(
        [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**标题：**{title}\n"
                        f"**平台：**{platform_label}\n"
                        f"**内容 ID：**{content_id}"
                    ),
                },
            },
            {
                "tag": "collapsible_panel",
                "expanded": False,
                "header": {"title": {"tag": "plain_text", "content": "展开查看完整正文"}},
                "vertical_spacing": "8px",
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": body or "（正文为空）"}}
                ],
            },
        ]
    )
    if hashtags:
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**标签：**{' '.join(hashtags)}"},
            }
        )
    elements.append(
        {
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "批准并自动发布"},
                    "type": "primary",
                    "value": {"action": "approve_publish", "content_id": content_id},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "拒绝"},
                    "type": "danger",
                    "value": {"action": "reject_publish", "content_id": content_id},
                },
            ],
        }
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green",
            "title": {"tag": "plain_text", "content": "图文已就绪，等待发布审批"},
        },
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
    """Build a Feishu approval card for a generated video asset."""
    elements: list[dict] = []
    if cover_url:
        elements.append(
            {
                "tag": "img",
                "img_key": cover_url,
                "alt": {"tag": "plain_text", "content": f"{topic} 视频封面"},
            }
        )
    elements.extend(
        [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**内容 ID：**{content_id}\n**视频时长：**{duration} 秒",
                },
            },
            {
                "tag": "collapsible_panel",
                "expanded": False,
                "header": {"title": {"tag": "plain_text", "content": "展开查看完整脚本"}},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": script}}],
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "下载视频"},
                        "url": video_url,
                        "type": "default",
                    },
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
            },
        ]
    )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "purple",
            "title": {"tag": "plain_text", "content": f"🎬 视频生成完成：{topic}"},
        },
        "elements": elements,
    }


def build_douyin_card_package_card(
    content_id: str,
    topic: str,
    image_keys: list[str],
    caption: str,
    hashtags: list[str],
) -> dict:
    """Build the ordered, manual-upload delivery card for Douyin images."""
    total = len(image_keys)
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**选题：**{topic}\n**内容 ID：**{content_id}\n"
                    f"**图片数量：**{total} 张\n**发布方式：**按下列顺序手动上传抖音图文"
                ),
            },
        },
        {"tag": "hr"},
    ]

    for index, image_key in enumerate(image_keys, start=1):
        role = "封面" if index == 1 else ("总结页" if index == total else f"正文卡片 {index - 1}")
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{index:02d} / {total:02d} · {role}**"},
            }
        )
        elements.append(
            {"tag": "img", "img_key": image_key, "alt": {"tag": "plain_text", "content": role}}
        )

    if caption:
        elements.extend(
            [
                {"tag": "hr"},
                {
                    "tag": "collapsible_panel",
                    "expanded": False,
                    "header": {"title": {"tag": "plain_text", "content": "展开复制抖音文案"}},
                    "vertical_spacing": "8px",
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": caption}}],
                },
            ]
        )
    if hashtags:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**标签：**{' '.join(hashtags)}"}}
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": f"抖音图文卡片已生成：{topic}"},
        },
        "elements": elements,
    }


def build_wechat_assets_card(
    content_id: str,
    title: str,
    assets: list[dict],
    draft_created: bool = False,
    draft_media_id: str = "",
    fallback_reason: str = "",
) -> dict:
    """Build a labeled WeChat image delivery card with insertion positions."""
    if draft_created:
        status = "已将封面和正文配图写入微信公众号草稿箱"
        if draft_media_id:
            status += f"\n**草稿 media_id：**{draft_media_id}"
    else:
        status = "未自动写入公众号草稿，请按下面标注手动插图"
        if fallback_reason:
            status += f"\n**原因：**{fallback_reason[:300]}"

    elements: list[dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**文章：**{title}\n**内容 ID：**{content_id}\n**交付状态：**{status}",
            },
        },
        {"tag": "hr"},
    ]

    inline_index = 0
    for asset in assets:
        role = str(asset.get("role") or "inline")
        if role == "cover":
            label = "封面图"
            position = "公众号封面（900×500）"
        else:
            inline_index += 1
            label = f"正文配图 {inline_index}"
            heading = str(asset.get("target_heading") or "对应正文小节")
            position = f"插在「{heading}」小节标题之后"

        alt_text = str(asset.get("alt_text") or "")
        details = f"**{label}**\n**使用位置：**{position}"
        if alt_text:
            details += f"\n**图片说明：**{alt_text}"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": details}})

        image_key = str(asset.get("image_key") or "")
        if image_key:
            elements.append(
                {"tag": "img", "img_key": image_key, "alt": {"tag": "plain_text", "content": label}}
            )
        else:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"图片上传飞书失败，服务器文件：{asset.get('image_path', '')}",
                    },
                }
            )
        elements.append({"tag": "hr"})

    if elements[-1].get("tag") == "hr":
        elements.pop()
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if draft_created else "orange",
            "title": {"tag": "plain_text", "content": "公众号文章配图交付"},
        },
        "elements": elements,
    }

