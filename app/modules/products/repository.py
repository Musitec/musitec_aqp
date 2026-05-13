from app.db.mongo import products_collection
from datetime import datetime
from zoneinfo import ZoneInfo
from bson import ObjectId
from bson.errors import InvalidId
from math import ceil

PERU_TZ = ZoneInfo("America/Lima")
PAGE_SIZE=8

async def expire_discounts_bulk():
    now = datetime.now(PERU_TZ)
    result = await products_collection.update_many(
        {
            "discount": {"$gt": 0},
            "stopDiscount": {"$lte": now}
        },
        {
            "$set": {
                "discount": 0,
                "startDiscount": None,
                "stopDiscount": None
            }
        }
    )
    return result.modified_count

async def get_product_by_id(product_id: str):
    try:
        return await products_collection.find_one(
            {"_id": ObjectId(product_id)}
        )
    except InvalidId:
        return None
    
async def increment_clicks(product_id: str):
    await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$inc": {"metrics.clicks": 1}}
    )

async def increment_search_hits(product_id: str):
    await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$inc": {"metrics.search_hits": 1}}
    )

async def get_active_discounted_products():
    await expire_discounts_bulk()
    products = []
    async for product in products_collection.find({
        "discount": {"$gt": 0},
        "is_active": True,
        "is_blocked": False
    }):
        products.append(product)
    return products

async def get_catalog_products(
    query_text: str | None = None,
    page=0,
    catalog="all",
    discount="all",
    order="popular"
):
    await expire_discounts_bulk()
    base_query = {"is_active": True, "is_blocked": False}
    common_query = base_query.copy()
    if query_text and query_text.strip():
        text = query_text.strip()
        common_query["$or"] = [
            {"name": {"$regex": text, "$options": "i"}},
            {"description": {"$regex": text, "$options": "i"}},
            {"catalog": {"$regex": text, "$options": "i"}},
            {"search_blob": {"$regex": text, "$options": "i"}}  # ✅ reemplazo correcto
        ]
    if discount == "with":
        common_query["discount"] = {"$gt": 0}
    if discount == "without":
        common_query["$and"] = common_query.get("$and", []) + [
            {
                "$or": [
                    {"discount": 0},
                    {"discount": {"$exists": False}}
                ]
            }
        ]
    products_query = common_query.copy()
    if catalog != "all":
        products_query["catalog"] = catalog
    total = await products_collection.count_documents(products_query)
    max_pages = ceil(total / PAGE_SIZE) if total else 0
    pipeline = [
        {"$match": products_query},
        {
            "$addFields": {
                "minPrice": {
                    "$cond": [
                        {"$gt": [{"$size": {"$ifNull": ["$variants", []]}}, 0]},
                        {
                            "$min": {
                                "$map": {
                                    "input": "$variants",
                                    "as": "v",
                                    "in": "$$v.price"
                                }
                            }
                        },
                        "$price"
                    ]
                }
            }
        }
    ]
    if order == "popular":
        pipeline.append({
            "$addFields": {
                "popularity": {
                    "$add": [
                        {"$multiply": ["$metrics.purchases", 5]},
                        {"$multiply": ["$metrics.clicks", 3]},
                        {"$multiply": ["$metrics.search_hits", 2]}
                    ]
                }
            }
        })
        pipeline.append({"$sort": {"popularity": -1}})
    elif order == "price_asc":
        pipeline.append({"$sort": {"minPrice": 1}})
    elif order == "price_desc":
        pipeline.append({"$sort": {"minPrice": -1}})
    else:
        pipeline.append({"$sort": {"createdAt": -1}})
    pipeline.extend([
        {"$skip": page * PAGE_SIZE},
        {"$limit": PAGE_SIZE}
    ])
    products = []
    async for p in products_collection.aggregate(pipeline):
        products.append(p)
    catalogs = await products_collection.distinct("catalog", common_query)
    return {
        "products": products,
        "catalogs": sorted(catalogs),
        "total": total,
        "max_pages": max_pages
    }

async def get_top_popular_products(limit: int):
    base_match = {
        "is_active": True,
        "is_blocked": False
    }
    pipeline = [
        {"$match": base_match},
        {"$addFields": {
            "popularity": {
                "$add": [
                    {"$multiply": ["$metrics.purchases", 5]},
                    {"$multiply": ["$metrics.clicks", 3]},
                    {"$multiply": ["$metrics.search_hits", 2]}
                ]
            }
        }},
        {"$sort": {"popularity": -1}},
        {"$limit": limit}
    ]
    popular = []
    async for p in products_collection.aggregate(pipeline):
        popular.append(p)
    if len(popular) < limit:
        missing = limit - len(popular)
        exclude_ids = [p["_id"] for p in popular]
        sample_pipeline = [
            {"$match": {
                **base_match,
                "_id": {"$nin": exclude_ids}
            }},
            {"$sample": {"size": missing}}
        ]
        async for p in products_collection.aggregate(sample_pipeline):
            popular.append(p)
    return popular

async def get_products_by_ids(product_ids: list[str]):
    object_ids = []
    for pid in product_ids:
        try:
            object_ids.append(ObjectId(pid))
        except:
            continue
    cursor = products_collection.find({
        "_id": {"$in": object_ids}
    })
    products = {}
    async for p in cursor:
        products[str(p["_id"])] = p
    return products