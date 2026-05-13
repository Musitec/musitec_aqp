from bson import ObjectId
from datetime import datetime, timezone
from dateutil import parser

from app.db.mongo import products_collection


def serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    return value


def ensure_datetime(value):
    """Convierte string ISO → datetime si es necesario"""
    if isinstance(value, str):
        try:
            return parser.isoparse(value)
        except Exception:
            return None
    return value


async def apply_discount_logic(product: dict, tz) -> dict:
    discount = product.get("discount", 0)
    stop = product.get("stopDiscount")
    time_left = 0
    now_utc = datetime.now(timezone.utc)
    if discount > 0 and stop:
        stop = ensure_datetime(stop)
        if not stop:
            product["discount"] = 0
            product["timeLeft"] = 0
            return product
        if stop.tzinfo is None:
            stop = stop.replace(tzinfo=timezone.utc)
        if stop <= now_utc:
            await products_collection.update_one(
                {"_id": product["_id"]},
                {
                    "$set": {
                        "discount": 0,
                        "startDiscount": None,
                        "stopDiscount": None
                    }
                }
            )
            product["discount"] = 0
            time_left = 0
        else:
            time_left = int((stop - now_utc).total_seconds())
        product["stopDiscount"] = stop.astimezone(tz).isoformat()
    product["timeLeft"] = max(time_left, 0)
    product.pop("startDiscount", None)
    product.pop("is_blocked", None)
    product.pop("is_active", None)
    product.pop("__v", None)
    product.pop("createdAt", None)
    product.pop("updatedAt", None)
    return product

async def serialize_product(product: dict, tz) -> dict:
    await apply_discount_logic(product, tz)
    return serialize_value(product)