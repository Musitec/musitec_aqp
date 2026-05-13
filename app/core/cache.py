from datetime import datetime, timedelta

PRODUCT_CACHE = {}
CACHE_TTL = timedelta(minutes=5)

def get_cached_product(product_id: str):
    entry = PRODUCT_CACHE.get(product_id)
    if not entry:
        return None
    if datetime.utcnow() > entry["expires_at"]:
        PRODUCT_CACHE.pop(product_id, None)
        return None
    return entry["data"]

def set_cached_product(product_id: str, data: dict):
    PRODUCT_CACHE[product_id] = {
        "data": data,
        "expires_at": datetime.utcnow() + CACHE_TTL
    }

def invalidate_product_cache(product_id: str):
    PRODUCT_CACHE.pop(product_id, None)