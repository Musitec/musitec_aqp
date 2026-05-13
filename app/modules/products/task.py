from app.db.mongo import products_collection
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
import random

DISCOUNTS = [10, 15, 20]
PERU_TZ = ZoneInfo("America/Lima")

def monday_midnight_of_week(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_local = now.astimezone(PERU_TZ)
    monday = now_local - timedelta(days=now_local.weekday())
    monday_local_midnight = datetime.combine(
        monday.date(),
        time(0, 0),
        tzinfo=PERU_TZ
    )
    return monday_local_midnight.astimezone(timezone.utc)

def next_monday_midnight(now: datetime) -> datetime:
    return monday_midnight_of_week(now) + timedelta(days=7)

async def count_current_weekly_discounts(now: datetime) -> int:
    start_week = monday_midnight_of_week(now)
    end_week = next_monday_midnight(now)
    return await products_collection.count_documents({
        "startDiscount": {"$gte": start_week, "$lt": end_week},
        "discount": {"$gt": 0}
    })

async def select_products_for_weekly_discount(limit: int):
    cursor = products_collection.find({
        "is_active": True,
        "is_blocked": False,
        "stock": {"$gt": 0},
        "discount": 0
    })
    products = [p async for p in cursor]
    random.shuffle(products)
    return products[:limit]

async def apply_weekly_discounts():
    now_utc = datetime.now(timezone.utc)
    start_week = monday_midnight_of_week(now_utc)
    end_week = next_monday_midnight(now_utc)
    current_count = await count_current_weekly_discounts(now_utc)
    if current_count >= 3:
        return {
            "applied": 0,
            "message": "Los descuentos semanales ya están completos"
        }
    missing = 3 - current_count
    products = await select_products_for_weekly_discount(missing)
    if not products:
        return {
            "applied": 0,
            "message": "No hay productos disponibles para descuento"
        }
    for product in products:
        await products_collection.update_one(
            {"_id": product["_id"]},
            {
                "$set": {
                    "discount": random.choice(DISCOUNTS),
                    "startDiscount": start_week,
                    "stopDiscount": end_week
                }
            }
        )
    return {
        "applied": len(products),
        "startDiscount": start_week.isoformat(),
        "stopDiscount": end_week.isoformat()
    }