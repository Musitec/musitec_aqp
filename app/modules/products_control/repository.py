from app.core.cache import invalidate_product_cache
from app.db.mongo import products_collection
from typing import Optional,List
from datetime import datetime,timezone
from bson import ObjectId

async def create_product(
    images: list,
    product_name: str,
    specifications: dict[str, str],
    description: str,
    price: Optional[float],
    stock: Optional[int],
    now: datetime,
    catalog: str,
    user: str,
    variants: Optional[list] = None,
):
    parts = []
    parts.append(product_name or "")
    parts.append(description or "")
    parts.append(catalog or "")
    if isinstance(specifications, dict):
        for k, v in specifications.items():
            parts.append(str(k))
            parts.append(str(v))
    search_blob = " ".join(parts).lower()
    product = {
        "name": product_name,
        "description": description,
        "images": images,
        "discount": 0,
        "specifications": specifications,
        "search_blob": search_blob,
        "createdAt": now,
        "updatedAt": now,
        "catalog": catalog,
        "is_active": True,
        "is_blocked": False,
        "startDiscount": None,
        "stopDiscount": None,
        "created_by": user,
        "metrics": {
            "clicks": 0,
            "search_hits": 0,
            "purchases": 0
        }
    }
    if variants:
        product["variants"] = variants
        product["price"] = None
        product["stock"] = None
    else:
        product["price"] = price
        product["stock"] = stock
    result = await products_collection.insert_one(product)
    return str(result.inserted_id)

async def update_product(product_id: str, data: dict):
    result = await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        data
    )
    invalidate_product_cache(product_id)
    return result

async def find_product_by_id(product_id: str):
    result = await products_collection.find_one({"_id": ObjectId(product_id)})
    return result

async def create_discount(
    product_id: str,
    discount: int,
    now: datetime,
    stopDiscount: datetime
):
    result = await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {
            "$set": {
                "discount": discount,
                "startDiscount": now,
                "stopDiscount": stopDiscount,
                "updatedAt": now
            }
        }
    )
    invalidate_product_cache(product_id)
    return result

async def update_stock_simple(product_id: str, new_stock: int, now: datetime):
    return await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {
            "$set": {
                "stock": new_stock,
                "updatedAt": now
            }
        }
    )

async def update_stock_variants(product_id: str, new_variants: list, now: datetime):
    return await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {
            "$set": {
                "variants": new_variants,
                "updatedAt": now
            }
        }
    )

async def delete_product(product_id: str):
    await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {
            "$set": {
                "is_active": False,
                "deletedAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc)
            }
        }
    )
    invalidate_product_cache(product_id)

async def delete_hard_product(product_id: str):
    await products_collection.delete_one(
        {"_id": ObjectId(product_id)}
    )

async def block_product(product_id: str, now:datetime):
    result=await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_blocked": True, "updatedAt": now}}
    )
    return result

async def unblock_product(product_id: str, now:datetime):
    result=await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_blocked": False, "updatedAt": now}}
    )
    return result

async def deactivate_product(product_id: str, now:datetime):
    result=await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_active": False, "updatedAt": now}}
    )
    return result
    
async def activate_product(product_id: str, now:datetime):
    result=await products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_active": True, "updatedAt": now}}
    )
    return result

def get_products_dashboard(match, sort, page, page_size, add_popularity):
    pipeline = []
    if match:
        pipeline.append({"$match": match})
    pipeline.append({
        "$addFields": {
            "computed_stock": {
                "$cond": {
                    "if": {"$isArray": "$variants"},
                    "then": {
                        "$sum": {
                            "$map": {
                                "input": "$variants",
                                "as": "v",
                                "in": {"$ifNull": ["$$v.stock", 0]}
                            }
                        }
                    },
                    "else": {"$ifNull": ["$stock", 0]}
                }
            },
            "computed_price": {
                "$cond": {
                    "if": {"$isArray": "$variants"},
                    "then": {
                        "$min": {
                            "$map": {
                                "input": "$variants",
                                "as": "v",
                                "in": {"$ifNull": ["$$v.price", 0]}
                            }
                        }
                    },
                    "else": {"$ifNull": ["$price", 0]}
                }
            }
        }
    })
    if add_popularity:
        pipeline.append({
            "$addFields": {
                "popularity": {
                    "$add": [
                        {"$multiply": [{"$ifNull": ["$metrics.purchases", 0]}, 5]},
                        {"$multiply": [{"$ifNull": ["$metrics.clicks", 0]}, 3]},
                        {"$multiply": [{"$ifNull": ["$metrics.search_hits", 0]}, 2]}
                    ]
                }
            }
        })
    pipeline.append({"$sort": sort})
    if page == 0:
        skip = 0
        limit = page_size - 1
    else:
        skip = (page_size - 1) + (page_size * (page - 1))
        limit = page_size
    pipeline.append({
        "$facet": {
            "data": [
                {"$skip": skip},
                {"$limit": limit}
            ],
            "totalCount": [
                {"$count": "count"}
            ]
        }
    })
    return products_collection.aggregate(pipeline)