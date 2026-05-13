from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from app.modules.products.task import apply_weekly_discounts
from app.modules.products.repository import expire_discounts_bulk
from app.core.config import settings

PERU_TZ = ZoneInfo("America/Lima")
scheduler = AsyncIOScheduler(timezone=PERU_TZ)
ENV = settings.ENV

async def start_scheduler():
    print("Scheduler iniciado (DEV)")
    if ENV == "development":
        interval_minutes = 1
    else:
        interval_minutes = 60
    scheduler.add_job(
        expire_discounts_bulk,
        "interval",
        minutes=1,
        id="cleanup_discounts",
        replace_existing=True
    )
    scheduler.add_job(
        apply_weekly_discounts,
        "interval",
        minutes=1,
        id="weekly_discounts",
        replace_existing=True
    )
    if settings.RUN_SCHEDULER == "true":
        scheduler.start()