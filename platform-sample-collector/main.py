import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree

import requests


SKILL_DIR = Path(__file__).resolve().parent
CACHE_PATH = SKILL_DIR / "cache" / "samples.json"
REQUEST_TIMEOUT = 12
DEFAULT_PLATFORMS = ["wechat", "douyin", "xhs"]
DEFAULT_KEYWORDS = ["准大一", "大学生", "人工智能", "AI", "科研", "项目", "社团", "校园", "招新"]
TARGET_TERMS = ["准大一", "新生", "大一", "大学生", "高考", "开学"]
AI_TERMS = ["AI", "人工智能", "大模型", "Agent", "智能体", "RAG", "科研", "项目", "论文"]
PSYCHOLOGY_TERMS = ["焦虑", "替代", "淘汰", "差距", "后悔", "错过", "迷茫", "价值", "竞争力", "过时"]

Sample = Dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_metrics(metrics: Dict[str, Any] | None) -> Dict[str, int]:
    metrics = metrics or {}
    return {
        "likes": safe_int(metrics.get("likes")),
        "comments": safe_int(metrics.get("comments")),
        "shares": safe_int(metrics.get("shares")),
        "favorites": safe_int(metrics.get("favorites")),
        "views": safe_int(metrics.get("views")),
    }


def safe_int(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def normalize_platform(value: str) -> str:
    value = str(value or "").lower().strip()
    mapping = {
        "公众号": "wechat",
        "微信": "wechat",
        "wechat": "wechat",
        "抖音": "douyin",
        "douyin": "douyin",
        "小红书": "xhs",
        "xhs": "xhs",
    }
    return mapping.get(value, value)


def summarize(text: str, max_length: int = 120) -> str:
    text = strip_html(text)
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def normalize_sample(raw: Dict[str, Any], default_platform: str = "") -> Sample:
    platform = normalize_platform(raw.get("platform") or default_platform)
    body = str(raw.get("body") or raw.get("content") or raw.get("description") or "")
    summary = str(raw.get("summary") or raw.get("excerpt") or summarize(body))
    title = str(raw.get("title") or raw.get("name") or "").strip()

    source_url = str(raw.get("source_url") or raw.get("url") or raw.get("link") or "")
    fingerprint = source_url or f"{platform}:{title}"
    return {
        "sample_id": str(raw.get("sample_id") or f"SMP-{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:12]}"),
        "platform": platform,
        "title": title,
        "summary": summary.strip(),
        "cover": str(raw.get("cover") or raw.get("cover_url") or raw.get("image") or ""),
        "hashtags": normalize_tags(raw.get("hashtags") or raw.get("tags") or raw.get("categories")),
        "published_at": str(raw.get("published_at") or raw.get("publish_time") or raw.get("pubDate") or ""),
        "source": str(raw.get("source") or platform),
        "source_url": source_url,
        "metrics": normalize_metrics(raw.get("metrics")),
        "account": str(raw.get("account") or raw.get("author") or ""),
        "author_followers": safe_int(raw.get("author_followers") or raw.get("followers")),
        "content_type": str(raw.get("content_type") or raw.get("carrier") or "unknown"),
        "cover_analysis": raw.get("cover_analysis") if isinstance(raw.get("cover_analysis"), dict) else {},
        "manual_review": str(raw.get("manual_review") or "pending"),
        "promotion_signal": bool(raw.get("promotion_signal", False)),
        "quality_status": "unchecked",
        "quality_score": 0.0,
        "data_status": str(raw.get("data_status") or "unknown"),
        "collected_at": str(raw.get("collected_at") or utc_now()),
    }


def normalize_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,，\s]+", value)
        return [part.strip() for part in parts if part.strip()]
    return []


def fetch_json_feed(url: str, platform: str) -> List[Sample]:
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    payload = resp.json()
    items = payload if isinstance(payload, list) else payload.get("data") or payload.get("items") or payload.get("list") or []
    samples = []
    for item in items:
        if isinstance(item, dict):
            item = dict(item)
            item.setdefault("platform", platform)
            item.setdefault("source_url", item.get("url") or item.get("link"))
            item["data_status"] = "live"
            samples.append(normalize_sample(item, platform))
    return samples


def fetch_rss_feed(url: str, platform: str) -> List[Sample]:
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    samples = []

    for item in root.findall(".//item"):
        raw = {
            "platform": platform,
            "title": text_or_empty(item.find("title")),
            "summary": strip_html(text_or_empty(item.find("description"))),
            "source_url": text_or_empty(item.find("link")),
            "published_at": text_or_empty(item.find("pubDate")),
            "hashtags": [text_or_empty(cat) for cat in item.findall("category")],
            "source": url,
            "data_status": "live",
        }
        samples.append(normalize_sample(raw, platform))

    atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", atom_ns):
        link = ""
        link_node = entry.find("atom:link", atom_ns)
        if link_node is not None:
            link = link_node.attrib.get("href", "")
        raw = {
            "platform": platform,
            "title": text_or_empty(entry.find("atom:title", atom_ns)),
            "summary": strip_html(text_or_empty(entry.find("atom:summary", atom_ns))),
            "source_url": link,
            "published_at": text_or_empty(entry.find("atom:updated", atom_ns)),
            "source": url,
            "data_status": "live",
        }
        samples.append(normalize_sample(raw, platform))

    return samples


def text_or_empty(node: Any) -> str:
    return "" if node is None or node.text is None else node.text.strip()


def fetch_feed(url: str, platform: str) -> List[Sample]:
    try:
        return fetch_json_feed(url, platform)
    except Exception:
        return fetch_rss_feed(url, platform)


def load_cache_samples(platforms: List[str]) -> List[Sample]:
    if not CACHE_PATH.exists():
        return []
    data = load_json(CACHE_PATH)
    raw_samples = data.get("samples", []) if isinstance(data, dict) else []
    return [
        normalize_sample({**item, "data_status": item.get("data_status", "cache")})
        for item in raw_samples
        if normalize_platform(item.get("platform")) in platforms
    ]


def collect_samples(input_data: Dict[str, Any], platforms: List[str]) -> tuple[List[Sample], List[str], List[str]]:
    samples: List[Sample] = []
    fetch_errors: List[str] = []
    degraded_platforms: List[str] = []

    input_samples = input_data.get("samples") or input_data.get("seed_samples") or []
    for item in input_samples:
        if isinstance(item, dict):
            sample = normalize_sample(item)
            if sample["platform"] in platforms:
                samples.append(sample)

    source_feeds = input_data.get("source_feeds") or {}
    for platform in platforms:
        before_count = len(samples)
        urls = source_feeds.get(platform, []) if isinstance(source_feeds, dict) else []
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            try:
                samples.extend(fetch_feed(url, platform))
            except Exception as e:
                fetch_errors.append(f"{platform}: {url}: {e}")
        if len(samples) == before_count and not any(item["platform"] == platform for item in samples):
            degraded_platforms.append(platform)

    cache_samples = load_cache_samples(platforms)
    if cache_samples:
        samples.extend(cache_samples)

    for platform in platforms:
        if not any(item["platform"] == platform for item in samples) and platform not in degraded_platforms:
            degraded_platforms.append(platform)

    return samples, fetch_errors, sorted(set(degraded_platforms))


def relevance_score(sample: Sample, keywords: List[str]) -> float:
    text = f"{sample.get('title', '')} {sample.get('summary', '')} {' '.join(sample.get('hashtags', []))}"
    score = 0.0
    for keyword in keywords:
        if keyword and keyword in text:
            score += 0.16
    for term in DEFAULT_KEYWORDS:
        if term in text:
            score += 0.08
    return round(min(1.0, score), 2)


def _contains_any(text: str, terms: List[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def score_breakdown(sample: Sample, keywords: List[str]) -> Dict[str, float]:
    """Score evidence, audience fit, engagement, visual value and transferability separately.

    Raw totals are deliberately not treated as proof of a transferable pattern: a large
    account, paid promotion or an unrelated celebrity topic can otherwise dominate the
    profile and contaminate all downstream prompts.
    """
    text = f"{sample.get('title', '')} {sample.get('summary', '')} {' '.join(sample.get('hashtags', []))}"
    metrics = sample.get("metrics", {})
    interactions = sum(metrics.get(key, 0) for key in ("likes", "comments", "shares", "favorites"))
    denominator = metrics.get("views") or sample.get("author_followers") or 0
    engagement_rate = min(1.0, interactions / denominator) if denominator else 0.0

    evidence = 0.0
    evidence += 0.35 if sample.get("source_url") else 0.0
    evidence += 0.20 if sample.get("published_at") else 0.0
    evidence += 0.25 if any(value > 0 for value in metrics.values()) else 0.0
    evidence += 0.20 if sample.get("data_status") in {"live", "manual_verified"} else 0.0

    audience_fit = 0.45 if _contains_any(text, TARGET_TERMS) else 0.0
    audience_fit += 0.40 if _contains_any(text, AI_TERMS) else 0.0
    audience_fit += min(0.15, relevance_score(sample, keywords) * 0.15)

    visual = 0.0
    visual += 0.35 if sample.get("cover") else 0.0
    cover = sample.get("cover_analysis") or {}
    visual += 0.25 if cover.get("composition") else 0.0
    visual += 0.20 if cover.get("headline") else 0.0
    visual += 0.20 if cover.get("style") or cover.get("visual_metaphor") else 0.0

    transferability = 0.45 if _contains_any(text, PSYCHOLOGY_TERMS) else 0.15
    transferability += 0.35 if _contains_any(text, AI_TERMS) else 0.0
    transferability += 0.20 if sample.get("content_type") in {"image_text", "carousel", "article", "unknown"} else 0.1

    anomaly_penalty = 0.0
    if sample.get("promotion_signal"):
        anomaly_penalty += 0.45
    if metrics.get("views", 0) and interactions > metrics.get("views", 0) * 1.2:
        anomaly_penalty += 0.35
    if sample.get("author_followers", 0) > 1_000_000 and engagement_rate < 0.003:
        anomaly_penalty += 0.20

    return {
        "evidence": round(min(1.0, evidence), 3),
        "audience_fit": round(min(1.0, audience_fit), 3),
        "engagement": round(min(1.0, engagement_rate * 12), 3),
        "visual": round(min(1.0, visual), 3),
        "transferability": round(min(1.0, transferability), 3),
        "anomaly_penalty": round(min(1.0, anomaly_penalty), 3),
    }


def quality_score(sample: Sample, keywords: List[str]) -> float:
    parts = score_breakdown(sample, keywords)
    score = (
        parts["evidence"] * 0.20
        + parts["audience_fit"] * 0.25
        + parts["engagement"] * 0.20
        + parts["visual"] * 0.20
        + parts["transferability"] * 0.15
        - parts["anomaly_penalty"]
    )
    return round(max(0.0, min(1.0, score)), 3)


def clean_samples(samples: List[Sample], keywords: List[str], max_samples: int) -> List[Sample]:
    seen = set()
    cleaned = []

    for sample in samples:
        title = sample.get("title", "").strip()
        source_url = sample.get("source_url", "").strip()
        key = source_url or f"{sample.get('platform')}:{title}"
        if not title or not source_url or key in seen:
            continue
        seen.add(key)

        sample["score_breakdown"] = score_breakdown(sample, keywords)
        sample["quality_score"] = quality_score(sample, keywords)
        if sample["quality_score"] < 0.42:
            sample["quality_status"] = "filtered_low_quality"
            continue
        sample["quality_status"] = "core" if sample.get("manual_review") == "approved" else "machine_shortlist"
        cleaned.append(sample)

    cleaned.sort(
        key=lambda item: (
            item.get("quality_score", 0),
            sum(item.get("metrics", {}).values()),
        ),
        reverse=True,
    )
    return cleaned[:max_samples]


def generate_result(input_data: Dict[str, Any]) -> Dict[str, Any]:
    platforms = [normalize_platform(item) for item in input_data.get("platforms", DEFAULT_PLATFORMS)]
    keywords = input_data.get("keywords") or DEFAULT_KEYWORDS
    max_samples = int(input_data.get("max_samples") or 100)

    raw_samples, fetch_errors, degraded_platforms = collect_samples(input_data, platforms)
    samples = clean_samples(raw_samples, keywords, max_samples)

    by_platform = {}
    core_by_platform = {}
    for platform in platforms:
        by_platform[platform] = len([item for item in samples if item.get("platform") == platform])
        core_by_platform[platform] = len([
            item for item in samples
            if item.get("platform") == platform and item.get("quality_status") == "core"
        ])

    return {
        "status": "success" if all(by_platform.get(item, 0) >= 3 for item in platforms) else "degraded",
        "collected_at": utc_now(),
        "platforms": platforms,
        "samples": samples,
        "raw_count": len(raw_samples),
        "valid_count": len(samples),
        "by_platform": by_platform,
        "core_by_platform": core_by_platform,
        "profile_eligible": all(core_by_platform.get(item, 0) >= 10 for item in platforms),
        "fetch_errors": fetch_errors,
        "degraded_platforms": degraded_platforms,
        "cache_used": any(item.get("data_status") == "cache" for item in samples),
        "notes": build_notes(platforms, by_platform, degraded_platforms) + [
            "machine_shortlist 仅供人工复核；只有 manual_review=approved 的 core 样本可进入正式画像。",
            "建议每个平台收集100条候选、机器筛选30条、人工确认10-15条核心样本，并按招新情绪类/AI技术类分层。",
        ],
    }


def build_notes(platforms: List[str], by_platform: Dict[str, int], degraded_platforms: List[str]) -> List[str]:
    notes = []
    for platform in platforms:
        if by_platform.get(platform, 0) == 0:
            notes.append(f"{platform} 暂无有效样本，需要补充公开 feed、历史缓存或真实平台来源。")
    if degraded_platforms:
        notes.append("部分平台发生降级，结果中已通过 degraded_platforms 标注。")
    return notes


def run(job_dir: str) -> int:
    job_dir_path = Path(job_dir)
    input_path = job_dir_path / "input.json"
    output_path = job_dir_path / "platform-sample-collector.json"
    logs_path = job_dir_path / "logs.txt"
    error_path = job_dir_path / "error.json"

    try:
        input_data = load_json(input_path)
        result = generate_result(input_data)
        library_dir = Path(
            input_data.get("samples_dir")
            or (Path(os.getenv("DATA_DIR", ".data")) / "samples")
        ).resolve()
        library_files = []
        for sample in result["samples"]:
            sample_path = library_dir / sample["platform"] / f"{sample['sample_id']}.json"
            write_json(sample_path, sample)
            library_files.append(str(sample_path))
        result["sample_library_dir"] = str(library_dir)
        result["sample_files"] = library_files
        write_json(output_path, result)
        logs_path.write_text(
            f"[success] platform-sample-collector finished. raw_count={result['raw_count']} valid_count={result['valid_count']}\n",
            encoding="utf-8",
        )
        return 0
    except Exception as e:
        write_json(error_path, {
            "status": "error",
            "generated_at": utc_now(),
            "error": str(e),
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
