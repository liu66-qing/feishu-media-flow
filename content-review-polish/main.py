import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_template.md"

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=4096
        )
        content = resp.choices[0].message.content or ""
        if content.strip():
            return content
    except Exception:
        pass

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096
    )
    return resp.choices[0].message.content or ""


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def parse_llm_json(raw):
    text = raw.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)

def score_original(original):
    title = original.get("title", "")
    body = original.get("body", "")
    cover_text = original.get("cover_text", "")

    hook = 3
    naturalness = 4
    depth = 3
    layout = 4

    weak_hook_words = ["分享一下", "简单说说", "一些想法", "随便聊聊"]
    marketing_words = ["绝对", "保证", "最", "第一", "必看", "赶紧"]

    if any(word in title for word in weak_hook_words):
        hook = 2

    if len(title) < 8:
        hook = min(hook, 2)

    if any(word in body for word in marketing_words):
        naturalness = 2

    if len(body) < 80:
        depth = 2

    if "\n" not in body and len(body) > 120:
        layout = 2

    overall = round((hook + naturalness + depth + layout) / 4, 1)

    return {
        "hook": hook,
        "naturalness": naturalness,
        "depth": depth,
        "layout": layout,
        "overall": overall
    }


def find_issues(score):
    issues = []

    if score["hook"] < 3:
        issues.append("标题或开头钩子偏弱")
    if score["naturalness"] < 3:
        issues.append("语言存在营销腔或绝对化表达")
    if score["depth"] < 3:
        issues.append("正文信息量偏少，内容深度不足")
    if score["layout"] < 3:
        issues.append("段落排版不清晰，阅读压力较大")

    return issues


def polish_title(title):
    if not title or len(title) < 8:
        return "社团招新前，先把这三件事想清楚"

    if "社团招新" in title:
        return "社团招新前，先把这三件事想清楚"

    replacements = {
        "分享一下": "认真整理了",
        "简单说说": "认真整理了",
        "一些想法": "几个真实建议",
        "随便聊聊": "一次完整复盘"
    }

    polished = title
    for old, new in replacements.items():
        polished = polished.replace(old, new)

    return polished


def polish_body(body, polish_level):
    polished = body

    replacements = {
        "大家一定要赶紧准备": "可以提前做一些准备",
        "这个方法绝对有用，可以保证效果变好": "这些方法能帮助你把现场流程理得更清楚",
        "绝对": "相对",
        "保证": "帮助",
        "必看": "建议看看",
        "赶紧": "可以先"
    }

    for old, new in replacements.items():
        polished = polished.replace(old, new)

    if "社团招新" in polished and "目标" not in polished:
        polished += (
            "\n\n可以先从三个问题开始：这次想吸引什么样的新生？"
            "现场谁负责介绍？活动结束后怎么继续沟通？"
        )

    if polish_level in ["medium", "heavy"]:
        polished = polished.replace("。", "。\n\n")

    if len(polished) < 100:
        polished += (
            "\n\n如果信息还不够完整，建议补充具体场景、真实例子或执行步骤。"
        )

    return polished


def polish_cover_text(cover_text, title):
    if cover_text:
        return cover_text[:12]
    return title[:12]


def polish_content_with_llm(input_data):
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY is not set")

    original = input_data.get("original", {})

    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "title": original.get("title", ""),
        "body": original.get("body", ""),
        "hashtags": json.dumps(original.get("hashtags", []), ensure_ascii=False),
        "cover_text": original.get("cover_text", ""),
        "polish_level": input_data.get("polish_level", "light")
    })

    raw = call_llm(prompt, system=system)

    if not raw.strip():
        raise ValueError("LLM returned empty content")

    data = parse_llm_json(raw)

    required_fields = [
        "quality_score",
        "issues",
        "polished",
        "changes_summary"
    ]

    for field in required_fields:
        if field not in data:
            raise ValueError(f"LLM output missing field: {field}")

    data["llm_enabled"] = True
    data["llm_error"] = ""

    return data

def polish_content(input_data):
    original = input_data.get("original", {})
    polish_level = input_data.get("polish_level", "light")

    score = score_original(original)
    issues = find_issues(score)

    title = original.get("title", "")
    body = original.get("body", "")
    hashtags = original.get("hashtags", [])
    cover_text = original.get("cover_text", "")

    polished_title = polish_title(title)
    polished_body = polish_body(body, polish_level)
    polished_cover_text = polish_cover_text(cover_text, polished_title)

    changes = []

    if polished_title != title:
        changes.append("优化了标题表达")
    if polished_body != body:
        changes.append("优化了正文表达和信息量")
    if polished_cover_text != cover_text:
        changes.append("补充或调整了封面文字")

    if not changes:
        changes.append("原文质量基本可用，仅做轻量检查")

    return {
        "quality_score": score,
        "issues": issues,
        "polished": {
            "title": polished_title,
            "body": polished_body,
            "hashtags": hashtags,
            "cover_text": polished_cover_text
        },
        "changes_summary": "；".join(changes)
    }


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "content_review_polish.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        try:
            data = polish_content_with_llm(input_data)
        except Exception as llm_error:
            data = polish_content(input_data)
            data["llm_enabled"] = False
            data["llm_error"] = str(llm_error)

        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": data
        }

        write_json(output_path, result)

        logs_path.write_text(
            f"[success] content-review-polish finished. overall={data['quality_score']['overall']}\n",
            encoding="utf-8"
        )

        return 0

    except Exception as e:
        error = {
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
        write_json(error_path, error)
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Path to job directory containing input.json")
    args = parser.parse_args()

    exit_code = run(args.job_dir)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()