import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.feishu import router as feishu_router
from app.api.health import router as health_router

logger = logging.getLogger(__name__)


async def _agent_recovery_loop():
    """Recover autonomous AgentLoop states and due publishes every 60 seconds."""
    from app.config import get_settings
    from app.services.agent_loop import AgentLoop

    await asyncio.sleep(10)  # wait for app startup
    settings = get_settings()

    while True:
        try:
            advanced = await AgentLoop(settings).advance_due_items()
            if advanced:
                logger.info("agent_recovery_loop: %d items advanced", advanced)
        except Exception as e:
            logger.error("agent_recovery_loop error: %s", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from app.config import get_settings

    recovery_task = None
    if get_settings().agent_recovery_enabled:
        recovery_task = asyncio.create_task(_agent_recovery_loop())
    try:
        yield
    finally:
        if recovery_task:
            recovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await recovery_task


def create_app() -> FastAPI:
    app = FastAPI(title="Feishu Media Flow", version="0.3.0", lifespan=_lifespan)
    app.include_router(health_router)
    app.include_router(feishu_router, prefix="/feishu", tags=["feishu"])
    app.include_router(agent_router)

    return app


app = create_app()

