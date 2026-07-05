from fastapi import FastAPI

from app.api.feishu import router as feishu_router
from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Feishu Media Flow", version="0.1.0")
    app.include_router(health_router)
    app.include_router(feishu_router, prefix="/feishu", tags=["feishu"])
    return app


app = create_app()

