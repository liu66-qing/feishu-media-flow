import importlib.util
import json
from pathlib import Path

from app.services.cards import build_douyin_card_package_card


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ai_prompt_keeps_mandatory_campus_constraints() -> None:
    image_compose = load_module("image_compose_test", ROOT / "image-compose" / "main.py")
    prompt = image_compose.build_ai_prompt("社团招新", "提高报名转化", "未来城市商务精英")
    assert "硬性身份与场景约束" in prompt
    assert "18至24岁的中国大学生" in prompt
    assert "中国大学校园" in prompt
    assert "禁止社会职场人士" in prompt
    assert "无任何文字" in prompt


def test_topic_selects_reusable_visual_system_and_allows_override() -> None:
    image_compose = load_module("image_compose_style_test", ROOT / "image-compose" / "main.py")

    assert image_compose.infer_visual_style("AI 展到底怎么看？") == "comic"
    assert image_compose.infer_visual_style("社团招新报名通知") == "editorial"
    assert image_compose.infer_visual_style("社团招新报名通知", "comic") == "comic"
    assert image_compose.infer_visual_style("AI 展到底怎么看？", "editorial") == "editorial"


def test_comic_topics_select_scene_variants() -> None:
    image_compose = load_module("image_compose_variant_test", ROOT / "image-compose" / "main.py")

    assert image_compose.infer_illustration_variant("A/B 两种方案对比") == "compare"
    assert image_compose.infer_illustration_variant("和同学沟通讨论") == "dialogue"
    assert image_compose.infer_illustration_variant("三种方法，大家一起完成") == "group"
    assert image_compose.infer_illustration_variant("最后总结", "summary") == "group"


def test_explicit_legacy_xhs_template_does_not_use_comic_prompt_style() -> None:
    image_compose = load_module("image_compose_legacy_test", ROOT / "image-compose" / "main.py")

    selected = image_compose.select_template(
        "学习",
        template_name="xhs-cover-03",
        text="AI 展到底怎么看？",
    )

    assert selected["template"] == "xhs-cover-03"
    assert selected["visual_style"] == "legacy_scene"


def test_video_cards_are_template_only_and_end_with_summary() -> None:
    video_generate = load_module("video_generate_test", ROOT / "video-generate" / "main.py")
    cards = video_generate.normalize_cards({"topic": "校园活动复盘"})
    assert len(cards) == 4
    assert cards[-1]["kind"] == "summary"
    assert all("素材" not in card["title"] for card in cards)


def test_douyin_card_set_keeps_one_topic_selected_visual_system(tmp_path, monkeypatch) -> None:
    image_compose = load_module("image_compose_group_test", ROOT / "image-compose" / "main.py")
    video_generate = load_module("video_generate_group_test", ROOT / "video-generate" / "main.py")

    def fake_run_job(render_dir: Path) -> dict:
        render_input = json.loads((render_dir / "input.json").read_text(encoding="utf-8"))
        output_path = render_dir / "output" / "rendered.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered-card")
        variables = render_input["variables"]
        return {
            "status": "success",
            "data": {
                "image_path": str(output_path),
                "template_used": render_input["template_name"],
                "visual_style_used": variables["visual_style"],
                "illustration_variant": variables["illustration_variant"],
            },
        }

    monkeypatch.setattr(image_compose, "run_job", fake_run_job)
    monkeypatch.setattr(video_generate, "load_image_compose_module", lambda: image_compose)
    payload = {
        "content_id": "CNT-DY-COMIC",
        "job_id": "JOB-DY-COMIC",
        "topic": "AI 展到底怎么看？",
        "selected_title": "AI 展到底怎么看？",
        "cards": [
            {
                "kind": "detail",
                "section_label": "对比一下",
                "title": "两种方案有什么区别",
                "body": "通过 A/B 对比看清差异。",
                "highlight": "先看切入点，再看取舍。",
            },
            {
                "kind": "detail",
                "section_label": "现场沟通",
                "title": "和同学讨论",
                "body": "提问并确认自己的理解。",
                "highlight": "把疑问问到底。",
            },
            {
                "kind": "summary",
                "section_label": "最后总结",
                "title": "带着问题去逛展",
                "body": "看产品、问问题、做对比。",
                "highlight": "形成自己的判断。",
            },
        ],
    }

    _, manifest = video_generate.render_card_set(payload, tmp_path)

    assert {card["visual_style"] for card in manifest} == {"comic"}
    assert all(card["template"].startswith("campus-comic-") for card in manifest)
    assert [card["illustration_variant"] for card in manifest[1:]] == [
        "compare",
        "dialogue",
        "group",
    ]


def test_douyin_content_cards_have_no_video_fields() -> None:
    content_generate = load_module(
        "content_generate_douyin_test",
        ROOT / "content-generate-douyin" / "main.py",
    )
    cards = content_generate.normalize_cards(
        [
            {
                "kind": "detail",
                "title": "先看问题",
                "body": "一页只讲一个重点。",
                "highlight": "结论要明确。",
                "voiceover": "旧字段应被删除",
                "duration": 8,
            },
            {"kind": "summary", "title": "总结", "body": "最后回顾。", "highlight": "照着做。"},
        ]
    )
    assert cards[-1]["kind"] == "summary"
    assert all("voiceover" not in card and "duration" not in card for card in cards)


def test_douyin_delivery_card_is_manual_image_upload_only() -> None:
    card = build_douyin_card_package_card(
        content_id="CNT-1",
        topic="校园活动复盘",
        image_keys=["img_cover", "img_body", "img_summary"],
        caption="校园活动复盘的三个重点。",
        hashtags=["#校园活动", "#大学生活"],
    )
    images = [element for element in card["elements"] if element.get("tag") == "img"]
    assert [item["img_key"] for item in images] == ["img_cover", "img_body", "img_summary"]
    serialized = str(card)
    assert "手动上传" in serialized
    assert "视频" not in serialized
    assert "approve_publish" not in serialized
