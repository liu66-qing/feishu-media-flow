"""Topic planner module — generates topic proposals for human approval."""

import json
import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from app.models import TopicBrief, TopicStatus, Platform
from app.services.llm import call_llm

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class Planner:
    """Analyzes schedule gaps and proposes topics."""

    def __init__(self, content_strategy: dict[str, str] | None = None) -> None:
        self._system_prompt = (PROMPTS_DIR / "planner_system.md").read_text(encoding="utf-8")
        self._strategy = content_strategy or {
            "account_positioning": "大学社团自媒体，分享校园经验、社团运营干货、大学生活",
            "tone": "年轻、真诚、不油腻",
            "audience": "大学生",
            "platforms": "xhs, wechat, douyin",
            "frequency": "每月4条（每平台）",
        }

    async def propose_topics(
        self,
        schedule_gap: int,
        recent_topics: list[str] | None = None,
        rejected_topics: list[str] | None = None,
    ) -> list[TopicBrief]:
        """Generate topic proposals based on schedule gaps."""
        user_msg = self._build_user_message(schedule_gap, recent_topics or [], rejected_topics or [])
        raw = await call_llm(self._system_prompt, user_msg, response_json=True)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Planner returned invalid JSON")
            return []

        topics = []
        for item in data.get("topics", []):
            platforms = [Platform(p) for p in item.get("target_platforms", ["xhs"]) if p in Platform.__members__.values()]
            brief = TopicBrief(
                topic_id=f"TOPIC-{uuid4().hex[:10]}",
                topic=item.get("topic", ""),
                angle=item.get("angle", ""),
                target_platforms=platforms or [Platform.XHS],
                key_points=item.get("key_points", []),
                status=TopicStatus.PROPOSED,
                created_at=datetime.now(),
            )
            topics.append(brief)

        logger.info("Planner proposed %d topics for gap of %d", len(topics), schedule_gap)
        return topics

    def _build_user_message(self, gap: int, recent: list[str], rejected: list[str]) -> str:
        parts = [
            f"## 账号定位\n{self._strategy.get('account_positioning', '')}",
            f"\n## 目标受众\n{self._strategy.get('audience', '')}",
            f"\n## 内容频率\n{self._strategy.get('frequency', '')}",
            f"\n## 当前排期缺口\n还需要 {gap} 条内容",
            f"\n## 目标平台\n{self._strategy.get('platforms', '')}",
        ]
        if recent:
            parts.append(f"\n## 近期已发布选题（避免重复）\n" + "\n".join(f"- {t}" for t in recent))
        if rejected:
            parts.append(f"\n## 已拒绝选题（不要再提）\n" + "\n".join(f"- {t}" for t in rejected))
        parts.append(f"\n## 请生成 {min(gap, 6)} 个选题建议")
        return "\n".join(parts)
