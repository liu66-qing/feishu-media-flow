import asyncio
import logging

from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.feishu import router as feishu_router
from app.api.health import router as health_router

logger = logging.getLogger(__name__)


async def _publish_loop():
    """Background loop: check for due content every 60s and publish."""
    from app.config import get_settings
    from app.services.bitable import BitableClient
    from app.services.notifier import FeishuNotifier
    from app.services.scheduler import publish_due_content

    await asyncio.sleep(10)  # wait for app startup
    settings = get_settings()
    store = BitableClient(settings)
    notifier = FeishuNotifier(settings)

    while True:
        try:
            results = await publish_due_content(settings, store, notifier)
            if results:
                logger.info("publish_loop: %d items processed", len(results))
        except Exception as e:
            logger.error("publish_loop error: %s", e)
        await asyncio.sleep(60)


def create_app() -> FastAPI:
    app = FastAPI(title="Feishu Media Flow", version="0.3.0")
    app.include_router(health_router)
    app.include_router(feishu_router, prefix="/feishu", tags=["feishu"])
    app.include_router(agent_router)

    @app.on_event("startup")
    async def start_publish_scheduler():
        asyncio.create_task(_publish_loop())

    return app


app = create_app()

