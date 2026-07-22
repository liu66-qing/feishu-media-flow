"""Evidence-first weekly performance reporting."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any


VERIFIED_STATUSES = {"live", "manual_verified", "creator_export", "api"}


def build_weekly_performance_report(records: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    week_start = (current - timedelta(days=current.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    observations: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        fields = record.get("fields", record)
        snapshots = _as_list(fields.get("metrics_snapshots", []))
        for snapshot in snapshots:
            observed_at = _parse_datetime(snapshot.get("observed_at"))
            if observed_at and observed_at < week_start:
                continue
            status = str(snapshot.get("data_status") or "unknown")
            if status not in VERIFIED_STATUSES:
                excluded.append(
                    {
                        "content_id": str(snapshot.get("content_id") or fields.get("content_id") or ""),
                        "checkpoint": str(snapshot.get("checkpoint") or ""),
                        "reason": f"unverified_data_status:{status}",
                    }
                )
                continue
            groups[(str(snapshot.get("platform") or fields.get("platform") or ""), str(snapshot.get("checkpoint") or ""))].append(snapshot)

    for (platform, checkpoint), items in sorted(groups.items()):
        totals: dict[str, int] = defaultdict(int)
        for item in items:
            for key, value in (item.get("metrics") or {}).items():
                totals[str(key)] += int(value or 0)
        observations.append(
            {
                "platform": platform,
                "checkpoint": checkpoint,
                "sample_size": len(items),
                "totals": dict(totals),
                "averages": {key: round(value / len(items), 2) for key, value in totals.items()},
                "claim_level": "observed_summary",
            }
        )

    hypotheses = []
    if sum(item["sample_size"] for item in observations) < 6:
        hypotheses.append(
            {
                "statement": "当前样本量不足以判断标题、封面、结构或发布时间与流量之间的稳定关系。",
                "next_test": "围绕一个变量建立至少两组同平台对照，并持续收集到72小时快照。",
                "status": "待验证",
            }
        )

    return {
        "week_start": week_start.isoformat(),
        "generated_at": current.isoformat(),
        "observations": observations,
        "verified_patterns": [],
        "hypotheses": hypotheses,
        "excluded_snapshots": excluded,
        "methodology": {
            "checkpoints": ["1h", "6h", "24h", "72h"],
            "verified_data_statuses": sorted(VERIFIED_STATUSES),
            "rule": "公开规则、观测汇总和待验证假设分开呈现；小样本不推断平台机制。",
        },
    }


def render_weekly_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 每周平台流量复盘",
        "",
        f"- 周起始：{report['week_start']}",
        f"- 生成时间：{report['generated_at']}",
        "",
        "## 已观测数据",
        "",
    ]
    if not report["observations"]:
        lines.append("本周没有通过来源校验的指标快照。")
    for item in report["observations"]:
        lines.append(
            f"- {item['platform']} / {item['checkpoint']}：样本 {item['sample_size']} 条，"
            f"均值 {item['averages']}"
        )
    lines.extend(["", "## 已验证规律", "", "暂无达到验证标准的规律。", "", "## 待验证假设", ""])
    for item in report["hypotheses"]:
        lines.append(f"- {item['statement']} 下一步：{item['next_test']}")
    lines.extend(["", "## 方法说明", "", report["methodology"]["rule"], ""])
    return "\n".join(lines)


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []
    return []


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
