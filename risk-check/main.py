import argparse
import json
from datetime import datetime
from pathlib import Path
import os
from openai import OpenAI

SKILL_DIR = Path(__file__).resolve().parent
RULES_PATH = SKILL_DIR / "rules" / "forbidden_words.json"

PROMPTS_DIR = SKILL_DIR / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system.md"
USER_TEMPLATE_PATH = PROMPTS_DIR / "user_template.md"

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
)


def call_llm(prompt, system="", model=None):
    model = model or os.getenv("LLM_MODEL", "gpt-5.4-mini")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
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
        ]
    )
    return resp.choices[0].message.content or ""

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


def read_text(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def render_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result

def run_llm_review(input_data):
    if not os.getenv("LLM_API_KEY"):
        return {
            "llm_concerns": [],
            "suggestions": [],
            "llm_enabled": False,
            "llm_error": "LLM_API_KEY is not set"
        }

    system = read_text(SYSTEM_PROMPT_PATH)
    template = read_text(USER_TEMPLATE_PATH)

    prompt = render_template(template, {
        "platform": input_data.get("platform", ""),
        "title": input_data.get("title", ""),
        "body": input_data.get("body", ""),
        "hashtags": " ".join(input_data.get("hashtags", []))
    })

    try:
        raw = call_llm(prompt, system=system)
        data = parse_llm_json(raw)

        return {
            "llm_concerns": data.get("llm_concerns", []),
            "suggestions": data.get("suggestions", []),
            "llm_enabled": True,
            "llm_error": ""
        }

    except Exception as e:
        return {
            "llm_concerns": [],
            "suggestions": [],
            "llm_enabled": True,
            "llm_error": str(e)
        }


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_context(text, word, window=20):
    index = text.find(word)
    if index == -1:
        return ""

    start = max(0, index - window)
    end = min(len(text), index + len(word) + window)
    return text[start:end]

def should_skip_hit(text, word, index):
    after = text[index + len(word): index + len(word) + 2]

    if word == "第一":
        safe_after_words = ["次", "次例", "步", "阶段", "轮", "章节", "部分", "个", "个区", "个区域", "关", "，", "、", "："]
        return any(after.startswith(safe_word) for safe_word in safe_after_words)

    if word == "最":
        safe_after_words = ["后", "近", "初", "终", "需要", "容易", "适合", "常见", "基础", "重要"]
        return any(after.startswith(safe_word) for safe_word in safe_after_words)

    return False


def collect_text_fields(input_data):
    fields = {
        "title": input_data.get("title", ""),
        "body": input_data.get("body", ""),
        "hashtags": " ".join(input_data.get("hashtags", [])),
    }
    return fields


def scan_forbidden_words(input_data, rules):
    hits = []
    fields = collect_text_fields(input_data)

    for rule_type, words in rules.items():
        for word in words:
            for location, text in fields.items():
                if word and word in text:
                    start_index = 0

                    while True:
                        index = text.find(word, start_index)
                        if index == -1:
                            break

                        if not should_skip_hit(text, word, index):
                            hits.append({
                                "word": word,
                                "type": rule_type,
                                "location": location,
                                "context": get_context(text, word)
                            })

                        start_index = index + len(word)

    return hits


def judge_risk_level(hits, llm_concerns=None):
    llm_concerns = llm_concerns or []
    hit_types = [hit["type"] for hit in hits]

    if "sensitive_domains" in hit_types or "political" in hit_types:
        return "high"

    if len(llm_concerns) >= 3:
        return "high"

    if "absolute_claims" in hit_types:
        return "medium"

    if len(llm_concerns) >= 1:
        return "medium"

    platform_risk_count = hit_types.count("platform_risk")
    if platform_risk_count > 2:
        return "medium"

    return "low"


def build_suggestions(hits):
    suggestions = []

    for hit in hits:
        if hit["type"] == "absolute_claims":
            suggestions.append(f"建议弱化「{hit['word']}」这类绝对化表达，改成更客观、可验证的说法。")
        elif hit["type"] == "platform_risk":
            suggestions.append(f"建议删除或替换「{hit['word']}」这类可能引流违规的表达。")
        elif hit["type"] == "sensitive_domains":
            suggestions.append(f"建议谨慎处理「{hit['word']}」相关内容，避免涉及敏感行业承诺。")
        elif hit["type"] == "political":
            suggestions.append(f"建议谨慎处理「{hit['word']}」相关内容，避免政治敏感风险。")

    return list(dict.fromkeys(suggestions))


def run(job_dir):
    job_dir = Path(job_dir)
    input_path = job_dir / "input.json"
    output_path = job_dir / "risk_check.json"
    logs_path = job_dir / "logs.txt"
    error_path = job_dir / "error.json"

    try:
        input_data = load_json(input_path)
        rules = load_json(RULES_PATH)

        hits = scan_forbidden_words(input_data, rules)
        local_suggestions = build_suggestions(hits)

        llm_review = run_llm_review(input_data)
        llm_concerns = llm_review["llm_concerns"]
        llm_suggestions = llm_review["suggestions"]

        risk_level = judge_risk_level(hits, llm_concerns)
        suggestions = local_suggestions + llm_suggestions

        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "content_id": input_data.get("content_id", ""),
            "data": {
                "risk_level": risk_level,
                "hits": hits,
                "llm_concerns": llm_concerns,
                "suggestions": suggestions,
                "llm_enabled": llm_review["llm_enabled"],
                "llm_error": llm_review["llm_error"]
            }
        }

        write_json(output_path, result)

        logs_path.write_text(
            f"[success] risk-check finished. risk_level={risk_level}, hits={len(hits)}\n",
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