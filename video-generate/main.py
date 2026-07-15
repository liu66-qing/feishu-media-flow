"""Generate an ordered Douyin image-card package.

The directory keeps its historical ``video-generate`` name so deployed
workflows do not need a migration. This module does not create video or audio.
"""

import argparse
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SKILL_DIR.parent
IMAGE_COMPOSE_MAIN = PROJECT_ROOT / "image-compose" / "main.py"
OUTPUT_NAME = "video-generate.json"
DEFAULT_SIZE = {"width": 1080, "height": 1350}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("input.json must be a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_log(job_dir: Path, message: str) -> None:
    with (job_dir / "logs.txt").open("a", encoding="utf-8") as file:
        file.write(f"[{utc_now()}] {message}\n")


def load_image_compose_module():
    spec = importlib.util.spec_from_file_location("campus_image_compose", IMAGE_COMPOSE_MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load image-compose from {IMAGE_COMPOSE_MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_cards = payload.get("cards")
    if not isinstance(raw_cards, list):
        generation = payload.get("generation")
        raw_cards = generation.get("cards") if isinstance(generation, dict) else []

    cards: list[dict[str, Any]] = []
    for index, raw in enumerate((raw_cards or [])[:7], start=1):
        if not isinstance(raw, dict):
            continue
        cards.append(
            {
                "kind": "summary" if str(raw.get("kind", "")).lower() == "summary" else "detail",
                "section_label": str(raw.get("section_label") or f"要点 {index}").strip()[:20],
                "title": str(raw.get("title") or "核心要点").strip()[:32],
                "body": str(raw.get("body") or "").strip()[:180],
                "highlight": str(raw.get("highlight") or "").strip()[:80],
            }
        )

    if not cards:
        topic = str(payload.get("topic") or "校园内容指南").strip()
        cards = [
            {
                "kind": "detail",
                "section_label": "先看问题",
                "title": "为什么总是没效果",
                "body": topic,
                "highlight": "先把问题说清楚，再谈方法。",
            },
            {
                "kind": "detail",
                "section_label": "方法一",
                "title": "抓住一个核心重点",
                "body": "每一页只表达一个结论，让读者能在三秒内看懂。",
                "highlight": "信息越聚焦，记忆越清楚。",
            },
            {
                "kind": "detail",
                "section_label": "方法二",
                "title": "用校园场景说人话",
                "body": "从大学生真实学习、社团与校园生活切入，不使用空泛素材。",
                "highlight": "真实语境比套话更有说服力。",
            },
            {
                "kind": "summary",
                "section_label": "快速回顾",
                "title": "最后记住这三点",
                "body": "01 一页一个重点\n02 使用校园语境\n03 结论必须可执行",
                "highlight": "把内容做成读得懂、记得住的卡片。",
            },
        ]
    cards[-1]["kind"] = "summary"
    return cards


def render_card_set(payload: dict[str, Any], job_dir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    image_compose = load_image_compose_module()
    output_dir = job_dir / "output"
    render_root = job_dir / "render"
    output_dir.mkdir(parents=True, exist_ok=True)
    render_root.mkdir(parents=True, exist_ok=True)

    cards = normalize_cards(payload)
    cover_lines = payload.get("cover_lines") or []
    if not isinstance(cover_lines, list):
        cover_lines = []
    title = "\n".join(str(item).strip() for item in cover_lines if str(item).strip())
    title = title or str(
        payload.get("cover_text") or payload.get("selected_title") or payload.get("topic") or "校园内容精选"
    )
    subtitle = str(payload.get("selected_title") or payload.get("subtitle") or payload.get("topic") or "").strip()
    base_variables = payload.get("variables") if isinstance(payload.get("variables"), dict) else {}
    brand_name = str(base_variables.get("brand_name") or "校园新媒体")
    series_name = str(base_variables.get("series_name") or "本期精选")
    footer = str(base_variables.get("footer") or "校园内容工作流")
    output_size = payload.get("output_size") if isinstance(payload.get("output_size"), dict) else DEFAULT_SIZE
    width = int(output_size.get("width") or DEFAULT_SIZE["width"])
    height = int(output_size.get("height") or DEFAULT_SIZE["height"])
    total = len(cards) + 1
    selection_text = " ".join(
        item for item in (
            str(payload.get("topic") or "").strip(),
            str(payload.get("selected_title") or "").strip(),
            str(payload.get("cover_text") or "").strip(),
            title,
            subtitle,
        ) if item
    )
    preferred_style = str(
        payload.get("visual_style") or base_variables.get("visual_style") or "auto"
    )
    template_set = image_compose.select_card_template_set(selection_text, preferred_style)
    visual_style = template_set["visual_style"]
    paper_color = str(base_variables.get("paper_color") or template_set["bg_color"])
    accent_color = str(base_variables.get("accent_color") or template_set["accent_color"])
    cover_bg_color = str(base_variables.get("cover_bg_color") or paper_color)
    cover_accent_color = str(base_variables.get("cover_accent_color") or accent_color)
    ai_all_cards = payload.get("ai_all_cards", base_variables.get("ai_all_cards", False)) is True
    requested_image_mode = str(payload.get("image_mode") or "template")

    render_specs: list[dict[str, Any]] = [
        {
            "template": template_set["cover"],
            "image_mode": requested_image_mode,
            "variables": {
                **base_variables,
                "title": title,
                "subtitle": subtitle if subtitle != title else "",
                "section_label": str(base_variables.get("section_label") or "校园主题精选"),
                "page_number": "01",
                "page_label": f"01 / {total:02d}",
                "brand_name": brand_name,
                "series_name": series_name,
                "footer": footer,
                "bg_color": cover_bg_color,
                "accent_color": cover_accent_color,
                "ai_prompt": str(base_variables.get("ai_prompt") or subtitle or title),
                "visual_style": visual_style,
                "template_role": "cover",
                "illustration_variant": image_compose.infer_illustration_variant(
                    selection_text, "cover"
                ),
            },
        }
    ]

    for index, card in enumerate(cards, start=2):
        is_summary = card["kind"] == "summary"
        render_specs.append(
            {
                "template": template_set["summary"] if is_summary else template_set["card"],
                "image_mode": requested_image_mode if ai_all_cards else "template",
                "variables": {
                    "title": card["title"],
                    "subtitle": card["section_label"] if is_summary else "",
                    "body": card["body"],
                    "highlight": card["highlight"],
                    "section_label": card["section_label"],
                    "page_number": f"{index:02d}",
                    "page_label": f"{index:02d} / {total:02d}",
                    "brand_name": brand_name,
                    "series_name": series_name,
                    "footer": footer,
                    "metric_label": str(card.get("metric_label") or "校园干货"),
                    "metric_value": str(card.get("metric_value") or f"要点 {index - 1}"),
                    "bg_color": paper_color,
                    "accent_color": accent_color,
                    "ai_prompt": str(card.get("ai_prompt") or f"{card['title']} {card['body']}"),
                    "visual_style": visual_style,
                    "template_role": "summary" if is_summary else "card",
                    "illustration_variant": image_compose.infer_illustration_variant(
                        f"{card['section_label']} {card['title']} {card['body']} {card['highlight']}",
                        "summary" if is_summary else "card",
                    ),
                },
            }
        )

    images: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for index, spec in enumerate(render_specs, start=1):
        render_dir = render_root / f"{index:02d}"
        render_dir.mkdir(parents=True, exist_ok=True)
        render_input = {
            "content_id": payload.get("content_id", ""),
            "job_id": f"{payload.get('job_id', 'JOB')}-CARD-{index:02d}",
            "template_name": spec["template"],
            "image_mode": spec["image_mode"],
            "variables": spec["variables"],
            "output_size": {"width": width, "height": height},
        }
        write_json(render_dir / "input.json", render_input)
        result = image_compose.run_job(render_dir)
        source_path = Path(result["data"]["image_path"])
        destination = output_dir / f"card_{index:02d}.png"
        shutil.copy2(source_path, destination)
        images.append(destination)
        manifest.append(
            {
                "index": index,
                "role": "cover" if index == 1 else ("summary" if index == total else "body"),
                "image_path": str(destination.resolve()),
                "template": result["data"].get("template_used", spec["template"]),
                "visual_style": result["data"].get("visual_style_used", visual_style),
                "illustration_variant": result["data"].get(
                    "illustration_variant", spec["variables"]["illustration_variant"]
                ),
                "label": f"{index:02d} / {total:02d}",
            }
        )
    return images, manifest


def run(job_dir: Path) -> int:
    error_path = job_dir / "error.json"
    try:
        payload = read_json(job_dir / "input.json")
        for required in ("content_id", "job_id", "topic"):
            if not str(payload.get(required) or "").strip():
                raise ValueError(f"missing required field: {required}")

        append_log(job_dir, "rendering ordered Douyin image cards")
        images, manifest = render_card_set(payload, job_dir)
        result = {
            "status": "success",
            "generated_at": utc_now(),
            "content_id": payload["content_id"],
            "job_id": payload["job_id"],
            "publish_mode": "manual_upload",
            "cover_path": str(images[0].resolve()),
            "card_paths": [str(path.resolve()) for path in images],
            "total_cards": len(images),
            "visual_style": manifest[0]["visual_style"],
            "caption": str(payload.get("body") or payload.get("caption") or "").strip(),
            "hashtags": payload.get("hashtags") if isinstance(payload.get("hashtags"), list) else [],
            "cards": manifest,
        }
        write_json(job_dir / OUTPUT_NAME, result)
        append_log(job_dir, f"Douyin card package generated: {len(images)} images")
        return 0
    except Exception as exc:
        write_json(error_path, {"status": "error", "generated_at": utc_now(), "error": str(exc)})
        append_log(job_dir, f"failed: {exc}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an ordered Douyin image-card package")
    parser.add_argument("--job-dir", required=True)
    args = parser.parse_args()
    raise SystemExit(run(Path(args.job_dir).resolve()))


if __name__ == "__main__":
    main()
