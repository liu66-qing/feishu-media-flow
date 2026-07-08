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
