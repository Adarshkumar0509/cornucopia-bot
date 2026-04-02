import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routes.webhook import router as webhook_router
from app.services.scheduler import SchedulerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = SchedulerService()
    task = asyncio.create_task(scheduler.run_daily())
    logger.info("Cornucopia bot started. Scheduler running.")
    yield
    task.cancel()
    logger.info("Cornucopia bot shutting down.")


app = FastAPI(
    title="Cornucopia GitHub Bot",
    description="GitHub bot for OWASP Cornucopia issue management",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook_router, prefix="/webhook", tags=["webhook"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "repo": f"{settings.repo_owner}/{settings.repo_name}"}
