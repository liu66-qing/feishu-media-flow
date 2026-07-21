import argparse
import json
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
DEFAULT_KEYWORDS = ["大学生", "社团", "校园", "招新", "新媒体", "活动", "运营"]

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

    return {
        "platform": platform,
        "title": title,
        "summary": summary.strip(),
        "cover": str(raw.get("cover") or raw.get("cover_url") or raw.get("image") or ""),
        "hashtags": normalize_tags(raw.get("hashtags") or raw.get("tags") or raw.get("categories")),
        "published_at": str(raw.get("published_at") or raw.get("publish_time") or raw.get("pubDate") or ""),
        "source": str(raw.get("source") or platform),
        "source_url": str(raw.get("source_url") or raw.get("url") or raw.get("link") or ""),
        "metrics": normalize_metrics(raw.get("metrics")),
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


def quality_score(sample: Sample, keywords: List[str]) -> float:
    score = relevance_score(sample, keywords)
    if sample.get("title"):
        score += 0.15
    if sample.get("summary"):
        score += 0.15
    if sample.get("source_url"):
        score += 0.15
    if sample.get("published_at"):
        score += 0.08
    if sample.get("cover"):
        score += 0.05
    if any(value > 0 for value in sample.get("metrics", {}).values()):
        score += 0.07
    return round(min(1.0, score), 2)


def clean_samples(samples: List[Sample], keywords: List[str], max_samples: int) -> List[Sample]:
    seen = set()
    cleaned = []

    for sample in samples:
        title = sample.get("title", "").strip()
        source_url = sample.get("source_url", "").strip()
        key = source_url or f"{sample.get('platform')}:{title}"
        if not title or key in seen:
            continue
        seen.add(key)

        sample["quality_score"] = quality_score(sample, keywords)
        if sample["quality_score"] < 0.35:
            sample["quality_status"] = "filtered_low_quality"
            continue
        sample["quality_status"] = "valid"
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
    max_samples = int(input_data.get("max_samples") or 30)

    raw_samples, fetch_errors, degraded_platforms = collect_samples(input_data, platforms)
    samples = clean_samples(raw_samples, keywords, max_samples)

    by_platform = {}
    for platform in platforms:
        by_platform[platform] = len([item for item in samples if item.get("platform") == platform])

    return {
        "status": "success",
        "collected_at": utc_now(),
        "platforms": platforms,
        "samples": samples,
        "raw_count": len(raw_samples),
        "valid_count": len(samples),
        "by_platform": by_platform,
        "fetch_errors": fetch_errors,
        "degraded_platforms": degraded_platforms,
        "cache_used": any(item.get("data_status") == "cache" for item in samples),
        "notes": build_notes(platforms, by_platform, degraded_platforms),
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
