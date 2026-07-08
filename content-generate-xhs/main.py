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
OUTPUT_NAME = "content-generate-xhs.json"
REQUIRED_FIELDS = ("content_id", "job_id", "topic")

# Load platform constraints
_CONSTRAINTS_FILE = SKILL_DIR.parent / "app" / "prompts" / "platform_constraints.json"
_XHS_CONSTRAINTS = {}
if _CONSTRAINTS_FILE.exists():
    import json as _json
    _XHS_CONSTRAINTS = _json.loads(_CONSTRAINTS_FILE.read_text(encoding="utf-8")).get("xhs", {})

SYSTEM_PROMPT = (
    "你是小红书内容共创编辑。整体风格年轻、真诚、不油腻，像真人分享经验。\n"
    '不要使用"建议""一定""绝对"这三个词，不要编造材料里没有的事实。\n'
    "所有回答必须是一个 JSON object。\n\n"
    "## 平台约束\n"
    f"- 标题：最多{_XHS_CONSTRAINTS.get('title_max_length', 20)}字\n"
    f"- 正文：{_XHS_CONSTRAINTS.get('body_min_length', 400)}-{_XHS_CONSTRAINTS.get('body_max_length', 900)}字\n"
    f"- 封面文案：最多{_XHS_CONSTRAINTS.get('cover_text_max_length', 15)}字\n"
    f"- 标签：最多{_XHS_CONSTRAINTS.get('max_tags', 10)}个\n"
    f"- 禁用词：{'、'.join(_XHS_CONSTRAINTS.get('forbidden_words', []))}\n\n"
    "## 风格要求\n"
    f"{_XHS_CONSTRAINTS.get('style_guide', '')}\n\n"
    "## 内容结构\n"
    f"{_XHS_CONSTRAINTS.get('content_structure', '')}"
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
    data.setdefault("brand", {})
    data.setdefault("column", "")
    if not isinstance(data["materials"], list):
        raise PipelineError("materials must be a list")
    if not isinstance(data["brand"], dict):
        raise PipelineError("brand must be an object")


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
        for name, value in {
            "LLM_API_KEY": api_key,
            "LLM_BASE_URL": base_url,
            "LLM_MODEL": model,
        }.items()
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

    last_error = ""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for attempt in range(2):
        if attempt == 1:
            messages.append(
                {
                    "role": "user",
                    "content": "上一轮没有得到可解析 JSON。只返回一个 JSON object，不要 Markdown，不要解释。",
                }
            )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4096,
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
    cover_text = str(final.get("cover_text") or context["step3_body"].get("cover_text") or "").strip()

    return {
        "content_id": job["content_id"],
        "job_id": job["job_id"],
        "title_options": titles[:3],
        "selected_title": str(final.get("selected_title") or (titles[0] if titles else "")).strip(),
        "body": body,
        "hashtags": hashtags[:8],
        "cover_text": cover_text,
        "risk_notes": list_of_strings(final.get("risk_notes")),
    }


def validate_output(result: dict[str, Any]) -> None:
    if not 1 <= len(result["title_options"]) <= 5:
        raise PipelineError("final output must contain 1-5 title_options")
    if result["selected_title"] not in result["title_options"]:
        result["selected_title"] = result["title_options"][0]
    if not 300 <= len(result["body"]) <= 1200:
        raise PipelineError(f"body must be 300-1200 characters, got {len(result['body'])}")
    if not 3 <= len(result["hashtags"]) <= 10:
        raise PipelineError("hashtags must contain 3-10 items")
    if not all(tag.startswith("#") for tag in result["hashtags"]):
        raise PipelineError("all hashtags must start with #")
    if not 4 <= len(result["cover_text"]) <= 20:
        raise PipelineError(f"cover_text must be 4-20 characters, got {len(result['cover_text'])}")


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
        write_json(
            error_path,
            {
                "status": "error",
                "generated_at": now_iso(),
                "error": str(exc),
            },
        )
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Xiaohongshu copy with a multi-step LLM pipeline.")
    parser.add_argument("--job-dir", required=True, help="Directory containing input.json")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.job_dir).resolve()))


if __name__ == "__main__":
    main()
