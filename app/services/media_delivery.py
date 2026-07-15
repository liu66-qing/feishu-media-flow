"""Platform media delivery executors without workflow or state ownership."""

import asyncio

from app.config import Settings
from app.models import Platform, SkillJob
from app.services.cards import build_douyin_card_package_card, build_wechat_assets_card
from app.services.notifier import FeishuNotifier
from app.services.skill_runner import SkillRunner


class MediaDeliveryService:
    """Build and deliver platform media while AgentLoop owns all transitions."""

    def __init__(
        self,
        settings: Settings,
        *,
        notifier: FeishuNotifier | None = None,
        runner: SkillRunner | None = None,
    ) -> None:
        self.settings = settings
        self.notifier = notifier or FeishuNotifier(settings)
        self.runner = runner or SkillRunner(settings)

    async def compose_douyin_cards(
        self,
        content_id: str,
        generation: dict,
        *,
        chat_id: str = "",
        use_ai_image: bool = False,
    ) -> dict:
        if not generation:
            await self.notifier.notify_admins(f"抖音卡片生成跳过：找不到 {content_id} 的内容结果")
            return {}

        topic = generation.get("selected_title") or generation.get("topic") or "校园内容"
        visual_style = str(generation.get("visual_style") or "auto")
        card_job = SkillJob(
            content_id=content_id,
            job_id=f"JOB-DY-CARDS-{content_id[4:]}",
            platform=Platform.DOUYIN,
            topic=topic,
            cards=generation.get("cards", []),
            cover_lines=generation.get("cover_lines", []),
            cover_text=generation.get("cover_text", ""),
            selected_title=generation.get("selected_title", topic),
            body=generation.get("body", ""),
            hashtags=generation.get("hashtags", []),
            image_mode="ai_bg" if use_ai_image else "template",
            visual_style=visual_style,
            variables={
                "brand_name": "校园新媒体",
                "series_name": "本期精选",
                "footer": "校园内容工作流",
                "ai_prompt": generation.get("selected_title", topic),
                "visual_style": visual_style,
            },
            output_size={"width": 1080, "height": 1350},
        )

        try:
            result = await asyncio.to_thread(self.runner.run, "video-generate", card_job)
            card_paths = result.get("card_paths", [])
            if not card_paths:
                raise RuntimeError("card package returned no card_paths")
            image_keys = await asyncio.gather(*(self.notifier.upload_image(path) for path in card_paths))
            if any(not key for key in image_keys):
                raise RuntimeError("one or more cards could not be uploaded to Feishu")
            card = build_douyin_card_package_card(
                content_id=content_id,
                topic=topic,
                image_keys=[str(key) for key in image_keys],
                caption=result.get("caption", ""),
                hashtags=result.get("hashtags", []),
            )
            delivery_chat_id = chat_id or self.settings.feishu_default_chat_id
            if delivery_chat_id:
                await self.notifier.send_card(delivery_chat_id, card)
            else:
                await self.notifier.notify_admins(
                    f"抖音图文卡片生成完成：{content_id}\n" + "\n".join(card_paths)
                )
            result["delivery_mode"] = "manual_upload"
            return result
        except Exception as exc:
            await self.notifier.notify_admins(f"抖音图文卡片生成失败：{content_id}\n{exc}")
            return {}

    async def compose_wechat_package(
        self,
        content_id: str,
        generation: dict,
        *,
        chat_id: str = "",
        use_ai_image: bool = True,
    ) -> dict:
        from app.services.wechat import WechatDraft, WechatDraftClient

        title = str(generation.get("selected_title") or generation.get("topic") or "校园内容")
        summary = str(generation.get("summary") or "")
        body_md = str(generation.get("body_md") or generation.get("body") or "")
        image_plan = self._normalize_wechat_image_plan(generation, title)

        async def render_asset(index: int, spec: dict) -> dict:
            is_cover = spec["role"] == "cover"
            compose_job = SkillJob(
                content_id=content_id,
                job_id=f"JOB-WX-IMG-{content_id[4:]}-{index:02d}",
                platform=Platform.WECHAT,
                topic=title,
                template_name="wechat-article-cover" if is_cover else "wechat-article-illustration",
                image_mode="ai_bg" if use_ai_image else "template",
                variables={
                    "brand_name": "校园新媒体",
                    "series_name": "公众号精选",
                    "section_label": "校园主题观察" if is_cover else "正文配图",
                    "title": spec["title"],
                    "subtitle": summary if is_cover else spec["alt_text"],
                    "highlight": spec["target_heading"],
                    "page_label": "WECHAT ARTICLE",
                    "footer": "校园内容工作流",
                    "bg_color": "#F7F4EE",
                    "accent_color": "#C94F32",
                    "ai_prompt": spec["prompt"],
                },
                output_size={"width": 900, "height": 500},
            )
            result = await asyncio.to_thread(self.runner.run, "image-compose", compose_job)
            image_path = result.get("data", {}).get("image_path", "")
            if not image_path:
                raise RuntimeError(f"image-compose returned no image for {spec['role']}")
            return {**spec, "image_path": image_path}

        rendered = await asyncio.gather(
            *(render_asset(index, spec) for index, spec in enumerate(image_plan, start=1)),
            return_exceptions=True,
        )
        assets: list[dict] = []
        render_errors: list[str] = []
        for item in rendered:
            if isinstance(item, Exception):
                render_errors.append(str(item))
            else:
                assets.append(item)

        image_keys = (
            await asyncio.gather(
                *(self.notifier.upload_image(asset["image_path"]) for asset in assets),
                return_exceptions=True,
            )
            if assets
            else []
        )
        for asset, image_key in zip(assets, image_keys):
            if isinstance(image_key, Exception):
                asset["image_key"] = ""
                render_errors.append(f"飞书图片上传失败：{image_key}")
            else:
                asset["image_key"] = image_key or ""

        draft_created = False
        draft_media_id = ""
        draft_error = ""
        cover = next((asset for asset in assets if asset["role"] == "cover"), None)
        inline_assets = [asset for asset in assets if asset["role"] == "inline"]
        if self.settings.wechat_app_id and self.settings.wechat_app_secret and cover:
            try:
                client = WechatDraftClient(self.settings)
                cover_media_id, inline_urls = await asyncio.gather(
                    client.upload_cover(cover["image_path"]),
                    asyncio.gather(*(client.upload_inline_image(asset["image_path"]) for asset in inline_assets)),
                )
                inline_images = [
                    {
                        "target_heading": asset["target_heading"],
                        "url": url,
                        "alt_text": asset["alt_text"],
                    }
                    for asset, url in zip(inline_assets, inline_urls)
                ]
                draft_result = await client.create_draft(
                    WechatDraft(
                        title=title,
                        author="校园新媒体",
                        digest=summary[:120],
                        content_markdown=body_md,
                        thumb_media_id=cover_media_id,
                        inline_images=inline_images,
                    )
                )
                draft_created = True
                draft_media_id = str(draft_result.get("media_id") or "")
            except Exception as exc:
                draft_error = str(exc)
        elif not (self.settings.wechat_app_id and self.settings.wechat_app_secret):
            draft_error = "未配置 WECHAT_APP_ID 或 WECHAT_APP_SECRET"
        elif not cover:
            draft_error = "封面图生成失败，无法创建公众号草稿"

        if render_errors:
            extra = "；".join(error[:160] for error in render_errors)
            draft_error = f"{draft_error}；部分配图失败：{extra}".strip("；")

        delivery_chat_id = chat_id or self.settings.feishu_default_chat_id
        if delivery_chat_id:
            await self.notifier.send_card(
                delivery_chat_id,
                build_wechat_assets_card(
                    content_id=content_id,
                    title=title,
                    assets=assets,
                    draft_created=draft_created,
                    draft_media_id=draft_media_id,
                    fallback_reason=draft_error,
                ),
            )
        elif not draft_created:
            await self.notifier.notify_admins(f"公众号文章配图已生成但无法发送：{content_id}\n{draft_error}")

        return {
            "cover_path": str(cover.get("image_path") or "") if cover else "",
            "card_paths": [str(asset.get("image_path") or "") for asset in inline_assets],
            "assets": assets,
            "draft_created": draft_created,
            "draft_media_id": draft_media_id,
            "draft_error": draft_error,
            "delivery_mode": "wechat_draft" if draft_created else "manual_insert",
        }

    @staticmethod
    def _normalize_wechat_image_plan(generation: dict, title: str) -> list[dict]:
        raw_plan = generation.get("image_plan")
        image_plan = raw_plan if isinstance(raw_plan, list) else []
        if not image_plan:
            sections = generation.get("sections") if isinstance(generation.get("sections"), list) else []
            headings = [str(item.get("heading") or "") for item in sections if isinstance(item, dict)]
            image_plan = [
                {
                    "role": "cover",
                    "title": title,
                    "prompt": title,
                    "target_heading": "公众号封面",
                    "alt_text": f"{title}封面图",
                },
                {
                    "role": "inline",
                    "title": headings[1] if len(headings) > 1 else "关键观察",
                    "prompt": f"{title}的校园场景信息图",
                    "target_heading": headings[1] if len(headings) > 1 else "关键观察",
                    "alt_text": f"{title}正文配图",
                },
                {
                    "role": "inline",
                    "title": headings[2] if len(headings) > 2 else "行动建议",
                    "prompt": f"{title}的校园行动建议海报",
                    "target_heading": headings[2] if len(headings) > 2 else "行动建议",
                    "alt_text": f"{title}行动建议配图",
                },
            ]

        normalized: list[dict] = []
        cover_seen = False
        inline_count = 0
        for raw in image_plan:
            if not isinstance(raw, dict):
                continue
            role = "cover" if str(raw.get("role") or "").lower() == "cover" else "inline"
            if role == "cover":
                if cover_seen:
                    continue
                cover_seen = True
            else:
                inline_count += 1
                if inline_count > 2:
                    continue
            normalized.append(
                {
                    "role": role,
                    "title": str(raw.get("title") or raw.get("target_heading") or title)[:42],
                    "prompt": str(raw.get("prompt") or title),
                    "target_heading": str(raw.get("target_heading") or "关键观察"),
                    "alt_text": str(raw.get("alt_text") or raw.get("title") or title),
                }
            )
        if not cover_seen:
            normalized.insert(
                0,
                {
                    "role": "cover",
                    "title": title,
                    "prompt": title,
                    "target_heading": "公众号封面",
                    "alt_text": f"{title}封面图",
                },
            )
        return normalized
