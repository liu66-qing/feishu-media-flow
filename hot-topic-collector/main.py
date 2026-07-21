import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


SKILL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_DIR / "prompts"
FILTER_PROMPT_PATH = PROMPTS_DIR / "filter_topics.md"

REQUEST_TIMEOUT = 10
DEFAULT_MAX_TOPICS = 10

_client = None


def get_llm_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "").strip(),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        )
    return _client


Topic = Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def parse_llm_json(raw: str) -> Dict[str, Any]:
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


def normalize_heat(value: Any, fallback: int) -> int:
    if isinstance(value, (int, float)):
        number = int(value)
    else:
        digits = re.sub(r"\D", "", str(value or ""))
        number = int(digits) if digits else fallback

    if number <= 100:
        return max(1, min(100, number))

    if number >= 10000000:
        return 100
    if number >= 1000000:
        return 95
    if number >= 100000:
        return 85
    if number >= 10000:
        return 75
    return max(1, min(100, number // 100))


def dedupe_topics(topics: List[Topic]) -> List[Topic]:
    seen = set()
    deduped = []

    for topic in topics:
        title = str(topic.get("title", "")).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        deduped.append(topic)

    return deduped


def fetch_weibo_hot() -> List[Topic]:
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://weibo.com/"
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    realtime = payload.get("data", {}).get("realtime", [])

    topics = []
    for index, item in enumerate(realtime, start=1):
        title = item.get("word") or item.get("note") or item.get("word_scheme") or ""
        title = str(title).strip("# ")
        if not title:
            continue
        topics.append({
            "title": title,
            "source": "weibo",
            "source_url": f"https://s.weibo.com/weibo?q={requests.utils.quote(title)}",
            "heat_score": normalize_heat(item.get("num") or item.get("raw_hot"), 100 - index),
            "rank": index,
            "data_status": "live",
            "collected_at": utc_now()
        })

    return topics


def fetch_vvhan_hot(platform: str, hot_type: str) -> List[Topic]:
    url = f"https://api.vvhan.com/api/hotlist?type={hot_type}"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    raw_items = payload.get("data") or payload.get("list") or []

    topics = []
    for index, item in enumerate(raw_items, start=1):
        title = item.get("title") or item.get("name") or item.get("word") or ""
        title = str(title).strip("# ")
        if not title:
            continue
        topics.append({
            "title": title,
            "source": platform,
            "source_url": item.get("url") or item.get("mobilUrl") or item.get("link") or "",
            "heat_score": normalize_heat(item.get("hot") or item.get("heat") or item.get("desc"), 100 - index),
            "rank": index,
            "data_status": "live",
            "collected_at": utc_now()
        })

    return topics


def collect_platform_topics(platform: str) -> List[Topic]:
    if platform == "weibo":
        return fetch_weibo_hot()
    if platform == "douyin":
        return fetch_vvhan_hot("douyin", "douyinHot")
    if platform == "xhs":
        return fetch_vvhan_hot("xhs", "xhsHot")
    return []


def seed_topics(platforms: List[str]) -> List[Topic]:
    seeds = [
        ("新生社团招新摊位怎么布置更吸引人", "weibo", 82),
        ("大学生做校园新媒体如何稳定更新", "xhs", 80),
        ("社团活动复盘模板火了", "xhs", 78),
        ("开学季社团招新短视频拍摄思路", "douyin", 77),
        ("校园活动没人参加怎么办", "weibo", 75),
        ("学生组织如何做成员分工", "xhs", 73),
        ("大学社团公众号选题怎么找", "weibo", 72),
        ("社团招新面试问题清单", "douyin", 71),
        ("校园摊位互动小游戏", "xhs", 70),
        ("新媒体部门第一次例会怎么开", "weibo", 69)
    ]
    allowed = set(platforms)
    return [
        {
            "title": title,
            "source": source,
            "source_url": "",
            "heat_score": heat,
            "rank": index,
            "data_status": "fallback",
            "collected_at": utc_now()
        }
        for index, (title, source, heat) in enumerate(seeds, start=1)
        if source in allowed
    ]


def collect_topics(platforms: List[str]) -> tuple[List[Topic], List[str], List[str]]:
    all_topics: List[Topic] = []
    errors = []
    degraded_platforms = []

    for platform in platforms:
        try:
            platform_topics = collect_platform_topics(platform)
            if platform_topics:
                all_topics.extend(platform_topics)
            else:
                degraded_platforms.append(platform)
        except Exception as e:
            errors.append(f"{platform}: {e}")
            degraded_platforms.append(platform)

    if not all_topics:
        all_topics = seed_topics(platforms)
    else:
        # 单个平台失败时，用明确标记的 fallback 选题补齐该平台，不影响其他平台 live 结果。
        all_topics.extend(seed_topics(degraded_platforms))

    return dedupe_topics(all_topics), errors, degraded_platforms


def keyword_relevance(title: str, keywords: List[str]) -> float:
    title_lower = title.lower()
    score = 0.0

    for keyword in keywords:
        keyword = str(keyword).strip()
        if keyword and keyword.lower() in title_lower:
            score += 0.22

    related_terms = ["招新", "活动", "校园", "学生", "社群", "新媒体", "公众号", "短视频", "组织", "复盘", "摊位"]
    for term in related_terms:
        if term in title:
            score += 0.08

    return round(min(1.0, score), 2)


def suggest_platform(title: str, source: str) -> str:
    if any(term in title for term in ["图文", "清单", "模板", "攻略", "复盘"]):
        return "xhs"
    if any(term in title for term in ["视频", "拍摄", "挑战", "现场"]):
        return "douyin"
    return source if source in {"xhs", "douyin", "weibo"} else "xhs"


def build_angle(title: str, keywords: List[str]) -> str:
    keyword_text = "、".join(keywords[:3]) or "社团运营"
    if "招新" in title:
        return "可以结合开学季招新，拆成摊位动线、互动话术和后续转化三个角度。"
    if "活动" in title:
        return "可以从活动策划复盘切入，讲清楚目标、分工、现场执行和复盘方法。"
    if "新媒体" in title or "公众号" in title or "短视频" in title:
        return "可以从社团新媒体内容生产切入，给出选题、排期和素材复用建议。"
    return f"可以把热点和{keyword_text}连接起来，做一篇面向大学生社团负责人的实用选题。"


def filter_topics_locally(topics: List[Topic], keywords: List[str], max_topics: int) -> List[Topic]:
    enriched = []

    for topic in topics:
        title = str(topic.get("title", ""))
        relevance = keyword_relevance(title, keywords)
        if relevance <= 0:
            continue
        enriched.append({
            "title": title,
            "source": topic.get("source", ""),
            "source_url": topic.get("source_url", ""),
            "heat_score": int(topic.get("heat_score", 0)),
            "relevance_score": relevance,
            "angle_suggestion": build_angle(title, keywords),
            "suggested_platform": suggest_platform(title, str(topic.get("source", ""))),
            "data_status": topic.get("data_status", "unknown"),
            "collected_at": topic.get("collected_at", utc_now())
        })

    enriched.sort(key=lambda item: (item["relevance_score"], item["heat_score"]), reverse=True)
    return enriched[:max_topics]


def call_llm_filter(topics: List[Topic], keywords: List[str], max_topics: int) -> List[Topic]:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")

    prompt_template = read_text(FILTER_PROMPT_PATH)
    prompt = (
        prompt_template
        .replace("{{keywords}}", json.dumps(keywords, ensure_ascii=False))
        .replace("{{max_topics}}", str(max_topics))
        .replace("{{topics}}", json.dumps(topics[:80], ensure_ascii=False, indent=2))
    )

    model = os.getenv("LLM_MODEL", "gpt-5.4-mini")
    resp = get_llm_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是校园新媒体和社团运营选题策划助手，只输出严格 JSON。"},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        max_tokens=4096
    )

    parsed = parse_llm_json(resp.choices[0].message.content or "")
    result_topics = parsed.get("topics", [])
    if not isinstance(result_topics, list):
        raise ValueError("LLM output topics is not a list")

    normalized = []
    for item in result_topics[:max_topics]:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        normalized.append({
            "title": str(item.get("title", "")),
            "source": str(item.get("source", "")),
            "source_url": str(item.get("source_url", "")),
            "heat_score": int(item.get("heat_score", 0) or 0),
            "relevance_score": float(item.get("relevance_score", 0) or 0),
            "angle_suggestion": str(item.get("angle_suggestion", "")),
            "suggested_platform": str(item.get("suggested_platform", "xhs")),
            "data_status": str(item.get("data_status", "unknown")),
            "collected_at": str(item.get("collected_at", utc_now()))
        })

    if not normalized:
        raise ValueError("LLM returned no usable topics")

    return normalized


def generate_result(input_data: Dict[str, Any]) -> Dict[str, Any]:
    keywords = input_data.get("keywords") or ["大学生", "社团", "运营", "校园", "新媒体"]
    platforms = input_data.get("platforms") or ["weibo", "douyin", "xhs"]
    max_topics = int(input_data.get("max_topics") or DEFAULT_MAX_TOPICS)

    raw_topics, fetch_errors, degraded_platforms = collect_topics(platforms)
    llm_enabled = False
    llm_error = ""

    try:
        filtered_topics = call_llm_filter(raw_topics, keywords, max_topics)
        llm_enabled = True
    except Exception as e:
        filtered_topics = filter_topics_locally(raw_topics, keywords, max_topics)
        llm_error = str(e)

    if len(filtered_topics) < min(max_topics, 8):
        supplement = filter_topics_locally(raw_topics + seed_topics(platforms), keywords, max_topics)
        existing_titles = {item["title"] for item in filtered_topics}
        for item in supplement:
            if item["title"] not in existing_titles:
                filtered_topics.append(item)
                existing_titles.add(item["title"])
            if len(filtered_topics) >= max_topics:
                break

    return {
        "collected_at": utc_now(),
        "topics": filtered_topics,
        "raw_count": len(raw_topics),
        "filtered_count": len(filtered_topics),
        "llm_enabled": llm_enabled,
        "llm_error": llm_error,
        "fetch_errors": fetch_errors,
        "degraded_platforms": degraded_platforms,
        "cache_used": any(item.get("data_status") == "fallback" for item in filtered_topics)
    }


def run(job_dir: str) -> int:
    job_dir_path = Path(job_dir)
    input_path = job_dir_path / "input.json"
    output_path = job_dir_path / "hot-topic-collector.json"
    logs_path = job_dir_path / "logs.txt"
    error_path = job_dir_path / "error.json"

    try:
        input_data = load_json(input_path)
        result = generate_result(input_data)
        write_json(output_path, result)

        logs_path.write_text(
            f"[success] hot-topic-collector finished. raw_count={result['raw_count']} filtered_count={result['filtered_count']}\n",
            encoding="utf-8"
        )
        return 0
    except Exception as e:
        write_json(error_path, {
            "status": "error",
            "generated_at": utc_now(),
            "error": str(e)
        })
        return 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Path to job directory containing input.json")
    args = parser.parse_args()

    exit_code = run(args.job_dir)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
