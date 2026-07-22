import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from simhash import Simhash


SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_template.md"

MAX_REWRITE_RETRIES = 2

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        max_tokens=4096
    )

    return resp.choices[0].message.content or ""


def parse_llm_json(raw):
    text = raw.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise


def tokenize_zh(text):
    cleaned = (
        text.replace("\n", "")
        .replace(" ", "")
        .replace("，", "")
        .replace("。", "")
        .replace("：", "")
        .replace("；", "")
        .replace("？", "")
        .replace("！", "")
        .replace("、", "")
        .replace("「", "")
        .replace("」", "")
        .replace("“", "")
        .replace("”", "")
        .replace("（", "")
        .replace("）", "")
        .replace('"', "")
        .replace("'", "")
    )

    tokens = []
    for size in (9, 10, 11, 12, 13, 14):
        for index in range(0, max(0, len(cleaned) - size + 1)):
            tokens.append(cleaned[index:index + size])

    if not tokens:
        tokens = list(cleaned)

    return tokens


def similarity(a, b):
    h1 = Simhash(tokenize_zh(a))
    h2 = Simhash(tokenize_zh(b))

    raw_score = 1 - (h1.distance(h2) / 64)
    normalized_score = max(0, (raw_score - 0.5) * 2)

    return round(normalized_score, 4), round(raw_score, 4)


def build_retry_hint(attempt, last_score):
    """为重试构建额外提示，要求 LLM 更大程度改变表达。"""
    return (
        f"\n\n注意：你上一次改写的相似度为 {last_score}，超过了 0.3 的阈值。"
        f"这是第 {attempt} 次重试（最多 {MAX_REWRITE_RETRIES} 次）。"
        "请务必从完全不同的角度、叙事结构和表达方式来改写，"
        "避免沿用原文的句式、段落顺序和关键词。"
    )


def call_rewrite_llm(input_data, retry_hint=""):
    """调用 LLM 进行改写，返回解析后的 JSON 数据。"""
    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "source_text": input_data.get("source_text", ""),
        "source_url": input_data.get("source_url", ""),
        "target_platform": input_data.get("target_platform", "xhs"),
        "target_column": input_data.get("target_column", "经验干货"),
        "rewrite_angle": input_data.get("rewrite_angle", "")
    })

    if retry_hint:
        prompt = prompt + retry_hint

    raw = call_llm(prompt, system=system)

    if not raw.strip():
        raise ValueError("LLM returned empty content")

    data = parse_llm_json(raw)

    # 兼容两种结构：顶层含 rewritten_content 或直接就是内容
    if "rewritten_content" in data and isinstance(data["rewritten_content"], dict):
        rewritten = data["rewritten_content"]
    else:
        rewritten = data

    for field in ["title", "body", "hashtags"]:
        if field not in rewritten:
            raise ValueError(f"LLM output missing field: {field}")

    # 提取 original_analysis（可能在顶层）
    original_analysis = data.get("original_analysis", {})

    return {
        "original_analysis": original_analysis,
        "rewritten_content": {
            "title": rewritten.get("title", ""),
            "body": rewritten.get("body", ""),
            "hashtags": rewritten.get("hashtags", [])
        }
    }


def generate_hot_rewrite(input_data):
    source = input_data.get("source") if isinstance(input_data.get("source"), dict) else {}
    source_text = str(
        input_data.get("source_text")
        or source.get("content")
        or source.get("body")
        or ""
    ).strip()
    source_title = str(input_data.get("source_title") or source.get("title") or "").strip()
    if source_title and source_title not in source_text:
        source_text = f"{source_title}\n{source_text}".strip()
    source_url = str(input_data.get("source_url") or source.get("url") or "")
    if len(source_text) < 50:
        raise ValueError("source_text must contain at least 50 characters of verifiable source content")
    input_data = dict(input_data)
    input_data["source_text"] = source_text
    input_data["source_url"] = source_url

    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY is not set")

    last_score = None
    llm_result = None

    for attempt in range(MAX_REWRITE_RETRIES + 1):
        retry_hint = ""
        if attempt > 0 and last_score is not None:
            retry_hint = build_retry_hint(attempt, last_score)

        llm_result = call_rewrite_llm(input_data, retry_hint=retry_hint)

        rewritten_content = llm_result["rewritten_content"]
        rewritten_text = rewritten_content["title"] + "\n" + rewritten_content["body"]
        similarity_score, _simhash_raw_score = similarity(source_text, rewritten_text)
        last_score = similarity_score

        if similarity_score <= 0.3:
            status = "success"
            risk_notes = []
            break
    else:
        # 重试次数用尽仍未通过
        status = "failed"
        risk_notes = [
            f"similarity_score={last_score}，经过 {MAX_REWRITE_RETRIES} 次重试后仍超过 0.3，"
            "改写结果与原文相似度过高，建议人工介入。"
        ]

    original_analysis = llm_result.get("original_analysis", {})

    return status, {
        "original_analysis": original_analysis,
        "rewritten_content": llm_result["rewritten_content"],
        "similarity_score": last_score,
        "similarity_method": "simhash_normalized_from_raw_baseline_0.5",
        "source_attribution": {
            "url": source_url,
            "note": "灵感来自原始内容，已重构角度、结构和表达方式。"
        },
        "risk_notes": risk_notes,
        "llm_enabled": True,
        "llm_error": ""
    }


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "hot_rewrite.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        status, data = generate_hot_rewrite(input_data)

        result = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": data
        }

        write_json(output_path, result)

        logs_path.write_text(
            f"[{status}] hot-rewrite finished. similarity_score={data['similarity_score']}\n",
            encoding="utf-8"
        )

        return 0 if status == "success" else 1

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
