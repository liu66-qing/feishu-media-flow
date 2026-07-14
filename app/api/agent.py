"""Agent tick endpoint — triggered by external cron or manual call."""

from fastapi import APIRouter

from app.config import get_settings
from app.services.agent_loop import AgentLoop

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/tick")
async def agent_tick() -> dict:
    """Main agent tick: plan if needed, advance due items, expire stale."""
    settings = get_settings()
    agent = AgentLoop(settings)
    return await agent.tick()


@router.post("/advance/{item_id}")
async def advance_item(item_id: str, reason: str = "manual") -> dict:
    """Manually advance a specific content item."""
    settings = get_settings()
    agent = AgentLoop(settings)
    return await agent.advance_item(item_id, reason=reason)


@router.post("/test/weekly-material")
async def test_weekly_material() -> dict:
    """[TEST] Force-send weekly material card regardless of weekday."""
    settings = get_settings()
    agent = AgentLoop(settings)
    topics = await agent._collect_weekly_topics()
    from app.services.cards import build_material_review_card
    card = build_material_review_card(topics)
    chat_id = settings.feishu_default_chat_id
    if not chat_id:
        return {"status": "error", "detail": "feishu_default_chat_id not set"}
    await agent.notifier.send_card(chat_id, card)
    return {"status": "sent", "topic_count": len(topics), "topics": [t.get("title") for t in topics]}
