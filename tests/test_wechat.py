import json

import httpx
import pytest

from app.config import Settings
from app.services.wechat import WechatDraft, WechatDraftClient, markdown_to_wechat_html


def test_markdown_to_wechat_html() -> None:
    html = markdown_to_wechat_html(
        "# 标题\n\n## 小节：校园观察\n- 要点\n正文 <script>",
        [
            {
                "target_heading": "小节",
                "url": "https://mmbiz.example/image?a=1&b=2",
                "alt_text": "校园配图",
            }
        ],
    )
    assert "<h1>标题</h1>" in html
    assert "<h2>小节：校园观察</h2>" in html
    assert "<p>• 要点</p>" in html
    assert 'src="https://mmbiz.example/image?a=1&amp;b=2"' in html
    assert "正文 &lt;script&gt;" in html


async def test_wechat_client_uploads_images_and_embeds_inline_url(tmp_path) -> None:
    captured_draft = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(200, json={"access_token": "token"})
        if request.url.path == "/cgi-bin/material/add_material":
            return httpx.Response(200, json={"media_id": "cover-media-id"})
        if request.url.path == "/cgi-bin/media/uploadimg":
            return httpx.Response(200, json={"url": "https://mmbiz.example/inline.png"})
        if request.url.path == "/cgi-bin/draft/add":
            captured_draft.update(json.loads(request.content))
            return httpx.Response(200, json={"media_id": "draft-media-id"})
        return httpx.Response(404)

    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"png")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.weixin.qq.com", transport=transport) as http_client:
        client = WechatDraftClient(
            Settings(wechat_app_id="app-id", wechat_app_secret="secret"),
            client=http_client,
        )
        cover_media_id = await client.upload_cover(image_path)
        inline_url = await client.upload_inline_image(image_path)
        result = await client.create_draft(
            WechatDraft(
                title="校园观察",
                author="校园新媒体",
                digest="摘要",
                content_markdown="# 校园观察\n\n## 关键变化\n正文",
                thumb_media_id=cover_media_id,
                inline_images=[
                    {
                        "target_heading": "关键变化",
                        "url": inline_url,
                        "alt_text": "正文配图",
                    }
                ],
            )
        )

    assert result["media_id"] == "draft-media-id"
    article = captured_draft["articles"][0]
    assert article["thumb_media_id"] == "cover-media-id"
    assert "https://mmbiz.example/inline.png" in article["content"]


async def test_wechat_draft_rejects_unmatched_image_position() -> None:
    client = WechatDraftClient(Settings(wechat_app_id="app-id", wechat_app_secret="secret"))
    client._access_token = "token"
    with pytest.raises(RuntimeError, match="target heading not found"):
        await client.create_draft(
            WechatDraft(
                title="校园观察",
                author="校园新媒体",
                digest="摘要",
                content_markdown="# 校园观察\n\n## 正文小节\n正文",
                thumb_media_id="cover-media-id",
                inline_images=[
                    {
                        "target_heading": "不存在的小节",
                        "url": "https://mmbiz.example/inline.png",
                        "alt_text": "正文配图",
                    }
                ],
            )
        )
