from app.services.wechat import markdown_to_wechat_html


def test_markdown_to_wechat_html() -> None:
    html = markdown_to_wechat_html("# 标题\n\n## 小节\n- 要点\n正文")
    assert "<h1>标题</h1>" in html
    assert "<h2>小节</h2>" in html
    assert "<p>• 要点</p>" in html
    assert "<p>正文</p>" in html

