"""Content quality critic with structured feedback and auto-revise loop."""

import json
import logging
from pathlib import Path
from typing import Any

from app.models import CriticFeedback, CriticScore, PlatformDraft, Platform
from app.services.llm import call_llm

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Platform preference profile path (V2 Schema)
_PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / ".data" / "profiles"

PASS_THRESHOLD = 20
REVISE_THRESHOLD = 15
MIN_DIMENSION_SCORE = 3
MAX_REVISIONS = 3


def load_platform_profile(platform: str) -> dict[str, Any] | None:
    """Load platform preference profile (V2 Schema). Returns None if not found or expired."""
    from datetime import datetime, timezone as _tz
    
    profile_file = _PROFILE_DIR / f"{platform}_profile.json"
    if not profile_file.exists():
        return None
    try:
        profile = json.loads(profile_file.read_text(encoding="utf-8"))
        # Check expiry (7 days)
        gen_at = profile.get("gen_at", "")
        if gen_at:
            gen_time = datetime.fromisoformat(gen_at)
            if gen_time.tzinfo is None:
                gen_time = gen_time.replace(tzinfo=_tz.utc)
            age_days = (datetime.now(_tz.utc) - gen_time).days
            if age_days >= 7:
                return None
        return profile
    except Exception:
        return None


class Critic:
    """Evaluates content quality and provides structured revision feedback."""

    def __init__(self) -> None:
        self._system_prompt = (PROMPTS_DIR / "critic_system.md").read_text(encoding="utf-8")
        self._user_template = (PROMPTS_DIR / "critic_user_template.md").read_text(encoding="utf-8")

    async def evaluate(self, draft: PlatformDraft, context: dict[str, str] | None = None) -> CriticFeedback:
        """Run one round of critique on a platform draft."""
        ctx = context or {}
        previous_feedback = ""
        if draft.critic_history:
            last = draft.critic_history[-1]
            previous_feedback = json.dumps(
                {"decision": last.decision, "revision_prompt": last.revision_prompt, "change": last.change},
                ensure_ascii=False,
            )

        user_msg = self._user_template.replace("{{platform}}", _platform_label(draft.platform))
        user_msg = user_msg.replace("{{content_goal}}", ctx.get("content_goal", "经验分享"))
        user_msg = user_msg.replace("{{target_audience}}", ctx.get("target_audience", "大学生"))
        user_msg = user_msg.replace("{{account_positioning}}", ctx.get("account_positioning", "社团自媒体"))
        user_msg = user_msg.replace("{{title}}", draft.content.get("title", ""))
        user_msg = user_msg.replace("{{draft_text}}", draft.content.get("body", ""))
        user_msg = user_msg.replace("{{hashtags}}", ", ".join(draft.content.get("hashtags", [])))
        user_msg = user_msg.replace("{{cover_text}}", draft.content.get("cover_text", ""))
        user_msg = user_msg.replace("{{revision_round}}", str(draft.revision_count + 1))
        user_msg = user_msg.replace("{{previous_feedback}}", previous_feedback or "无（首轮评审）")

        profile = load_platform_profile(draft.platform.value)
        if profile:
            user_msg += (
                "\n\n## 当前平台动态偏好画像（仅作为有样本依据的评审补充）\n"
                f"画像版本：{profile.get('v', '')}\n"
                f"样本数：{profile.get('s_cnt', 0)}\n"
                f"置信度：{profile.get('conf', 0)}\n"
                f"偏好：{json.dumps(profile, ensure_ascii=False)}"
            )

        raw = await call_llm(self._system_prompt, user_msg, response_json=True)
        return self._parse_response(raw)

    async def critique_loop(self, draft: PlatformDraft, revise_fn, context: dict[str, str] | None = None) -> CriticFeedback:
        """Run evaluate → revise loop up to MAX_REVISIONS times.

        revise_fn: async callable(draft, feedback) -> updated draft content dict
        Returns the final CriticFeedback (pass, or last revise/reject after exhausting rounds).
        """
        for round_num in range(MAX_REVISIONS + 1):
            feedback = await self.evaluate(draft, context)
            draft.critic_history.append(feedback)

            if feedback.decision == "pass":
                logger.info("Draft %s passed on round %d", draft.draft_id, round_num + 1)
                return feedback

            if feedback.decision == "reject":
                logger.info("Draft %s rejected: %s", draft.draft_id, feedback.revision_prompt)
                return feedback

            if round_num >= MAX_REVISIONS:
                logger.warning("Draft %s exhausted %d revision rounds", draft.draft_id, MAX_REVISIONS)
                return feedback

            # Check for score stagnation
            if len(draft.critic_history) >= 2:
                prev_total = draft.critic_history[-2].scores.total
                curr_total = feedback.scores.total
                if curr_total <= prev_total:
                    logger.warning("Draft %s score not improving (%d -> %d), stopping", draft.draft_id, prev_total, curr_total)
                    return feedback

            # Revise
            draft.revision_count += 1
            new_content = await revise_fn(draft, feedback)
            draft.content = new_content
            draft.version += 1

        return draft.critic_history[-1]

    def _parse_response(self, raw: str) -> CriticFeedback:
        """Parse LLM JSON response into CriticFeedback."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Critic returned invalid JSON, treating as reject")
            return CriticFeedback(
                decision="reject",
                scores=CriticScore(hook=1, information_density=1, naturalness=1, platform_fit=1, actionability=1),
                revision_prompt="Critic无法解析评审结果，请重新生成",
            )

        scores_raw = data.get("scores", {})
        scores = CriticScore(
            hook=scores_raw.get("structure_and_flow", {}).get("score", 3),
            information_density=scores_raw.get("value_density", {}).get("score", 3),
            naturalness=scores_raw.get("originality_and_voice", {}).get("score", 3),
            platform_fit=scores_raw.get("platform_fit", {}).get("score", 3),
            actionability=scores_raw.get("publish_readiness", {}).get("score", 3),
        )

        # Apply decision rules
        decision = data.get("decision", "revise")
        if scores.total >= PASS_THRESHOLD and scores.min_score >= MIN_DIMENSION_SCORE:
            decision = "pass"
        elif scores.total < REVISE_THRESHOLD or scores.min_score < 2:
            decision = "reject"

        return CriticFeedback(
            decision=decision,
            scores=scores,
            blocking_issues=[
                {"dimension": p["dimension"], "quote": p.get("quote", ""), "problem": p["problem"], "fix_direction": p["fix_direction"]}
                for p in data.get("problems", [])
                if p.get("severity") == "high"
            ],
            keep=[item.get("quote", "") for item in data.get("what_to_keep", [])],
            change=[item["task"] for item in data.get("revision_priority", [])],
            revision_prompt=data.get("revision_prompt", ""),
        )


def _platform_label(platform: Platform) -> str:
    return {"xhs": "小红书", "wechat": "公众号", "douyin": "抖音"}.get(platform.value, platform.value)
