import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
OUTPUT_NAME = "content-generate-douyin.json"
REQUIRED_FIELDS = ("content_id", "job_id", "topic")

SYSTEM_PROMPT = (
    "你是抖音图文内容创作者。风格成熟、真实、有信息增量，像一个有经验的人在复盘分享。\n"
    "不要使用小红书风格（emoji堆砌、符号装饰、'姐妹们'等）。\n"
    "不要营销腔、不要编造事实、不要夸大承诺。\n"
    "所有回答必须是一个 JSON object。\n\n"
    "## 平台约束\n"
    "- 正文：600-1500字\n"
    "- 封面大字：2-4行，每行3-7字\n"
    "- 标签：3-6个\n"
    "- 标题：口语化，有悬念或冲突感\n\n"
    "## 风格要求\n"
    "- 开头必须有真实场景代入\n"
    "- 结尾有编号建议（3-5条）\n"
    "- 段落间有停顿感，每段2-4句\n"
    "- 语气直接、不油腻"
)


class PipelineError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PipelineError(f"missing input file: {path}")
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise PipelineError("input.json must be a JSON object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_fields(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise PipelineError(f"missing required field(s): {', '.join(missing)}")
    data.setdefault("materials", [])
    data.setdefault("column", "")


def read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise PipelineError(f"missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")
    return data


def build_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    missing = [
        name
        for name, value in {"LLM_API_KEY": api_key, "LLM_BASE_URL": base_url, "LLM_MODEL": model}.items()
        if not value
    ]
    if missing:
        raise PipelineError(f"missing environment variable(s): {', '.join(missing)}")
    return OpenAI(api_key=api_key, base_url=base_url), str(model)


def call_step(
    client: OpenAI,
    model: str,
    step_name: str,
    prompt: str,
    job: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": prompt
            + "\n\n输入与上文 JSON：\n"
            + json.dumps({"input": job, "context": context}, ensure_ascii=False, indent=2),
        },
    ]

    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    last_error = ""
    for attempt in range(2):
        if attempt == 1:
            messages.append(
                {"role": "user", "content": "上一轮没有得到可解析 JSON。只返回一个 JSON object，不要 Markdown，不要解释。"}
            )
        response = client.chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}, max_tokens=4096
        )
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        raw = response.choices[0].message.content or ""
        try:
            parsed = parse_json_object(raw)
            return parsed, {
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "tokens": usage,
                "attempts": attempt + 1,
                "status": "ok",
            }
        except Exception as exc:
            last_error = f"{exc}; raw_preview={raw[:500]}"

    raise PipelineError(f"{step_name} failed after retry: {last_error}")


def list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_final(job: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    review = context["step4_review"]
    final = review.get("final") if isinstance(review.get("final"), dict) else review
    titles = list_of_strings(final.get("title_options") or context["step2_titles"].get("title_options"))
    hashtags = list_of_strings(final.get("hashtags") or context["step3_body"].get("hashtags"))
    body = str(final.get("body") or context["step3_body"].get("body") or "").strip()
    cover_lines = list_of_strings(final.get("cover_lines") or context["step2_titles"].get("cover_lines"))

    return {
        "content_id": job["content_id"],
        "job_id": job["job_id"],
        "title_options": titles[:3],
        "selected_title": str(final.get("selected_title") or (titles[0] if titles else "")).strip(),
        "body": body,
        "hashtags": hashtags[:6],
        "cover_lines": cover_lines[:4],
        "cover_text": " ".join(cover_lines[:4])[:20] if cover_lines else "",
        "risk_notes": list_of_strings(final.get("risk_notes")),
    }


def validate_output(result: dict[str, Any]) -> None:
    if not 1 <= len(result["title_options"]) <= 5:
        raise PipelineError("final output must contain 1-5 title_options")
    if result["selected_title"] not in result["title_options"]:
        result["selected_title"] = result["title_options"][0]
    if not 400 <= len(result["body"]) <= 2000:
        raise PipelineError(f"body must be 400-2000 characters, got {len(result['body'])}")
    if not 2 <= len(result["hashtags"]) <= 8:
        raise PipelineError("hashtags must contain 2-8 items")
    if not all(tag.startswith("#") for tag in result["hashtags"]):
        raise PipelineError("all hashtags must start with #")
    if not 1 <= len(result["cover_lines"]) <= 5:
        raise PipelineError(f"cover_lines must have 1-5 items, got {len(result['cover_lines'])}")


def run(job_dir: Path) -> int:
    error_path = job_dir / "error.json"
    try:
        job = read_json(job_dir / "input.json")
        require_fields(job)
        client, model = build_client()

        context: dict[str, Any] = {}
        pipeline_log: dict[str, Any] = {}
        for step_name, prompt_file in [
            ("step1_analyze", "step1_analyze.md"),
            ("step2_titles", "step2_titles.md"),
            ("step3_body", "step3_body.md"),
            ("step4_review", "step4_review.md"),
        ]:
            parsed, log = call_step(client, model, step_name, read_prompt(prompt_file), job, context)
            context[step_name] = parsed
            pipeline_log[step_name] = log

        result = normalize_final(job, context)
        validate_output(result)
        result["pipeline_log"] = pipeline_log
        write_json(job_dir / OUTPUT_NAME, result)
        return 0
    except Exception as exc:
        write_json(error_path, {"status": "error", "generated_at": now_iso(), "error": str(exc)})
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Douyin image-text content with a multi-step LLM pipeline.")
    parser.add_argument("--job-dir", required=True, help="Directory containing input.json")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.job_dir).resolve()))


if __name__ == "__main__":
    main()
