from app.db.mongo import products_collection
from typing import Dict, Any

MIN_SIMILARITY_SCORE = 2
SIMILAR_PRODUCTS_LIMIT = 8

def normalize(value):
    if isinstance(value, str):
        return value.strip().lower()
    return value

def specifications_similarity(spec_a: Dict[str, Any], spec_b: Dict[str, Any]) -> int:
    score = 0
    common_keys = set(spec_a.keys()) & set(spec_b.keys())
    for key in common_keys:
        score += 1
        val_a = normalize(spec_a.get(key))
        val_b = normalize(spec_b.get(key))
        if val_a == val_b:
            score += 3
    return score

def get_candidate_products(base_product: dict):
    specs = base_product.get("specifications", {})
    if not specs:
        return None
    or_conditions = [
        {f"specifications.{key}": {"$exists": True}}
        for key in specs.keys()
    ]
    return products_collection.find({
        "$or": or_conditions,
        "_id": {"$ne": base_product["_id"]},
        "is_active": True,
        "is_blocked": False
    })

async def get_spec_similar_products(base_product, limit):
    base_specs = base_product.get("specifications", {})
    if not base_specs:
        return []
    or_conditions = [
        {f"specifications.{key}": {"$exists": True}}
        for key in base_specs
    ]
    cursor = products_collection.find({
        "$or": or_conditions,
        "_id": {"$ne": base_product["_id"]},
        "is_active": True,
        "is_blocked": False
    })
    scored = []
    async for product in cursor:
        score = specifications_similarity(
            base_specs,
            product.get("specifications", {})
        )
        if score >= MIN_SIMILARITY_SCORE:
            scored.append((score, product))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]

async def get_same_catalog_products(base_product, exclude_ids, limit):
    if not base_product.get("catalog"):
        return []
    cursor = products_collection.find({
        "catalog": base_product["catalog"],
        "_id": {"$nin": exclude_ids},
        "is_active": True,
        "is_blocked": False
    }).limit(limit)
    return [p async for p in cursor]

async def get_random_products(exclude_ids, limit):
    cursor = products_collection.aggregate([
        {
            "$match": {
                "_id": {"$nin": exclude_ids},
                "is_active": True,
                "is_blocked": False
            }
        },
        {"$sample": {"size": limit}}
    ])
    return [p async for p in cursor]

async def get_similar_products(base_product, limit=SIMILAR_PRODUCTS_LIMIT):
    results = []
    used_ids = {base_product["_id"]}

    spec_similar = await get_spec_similar_products(base_product, limit)
    for p in spec_similar:
        results.append(p)
        used_ids.add(p["_id"])
    if len(results) < limit:
        catalog_similar = await get_same_catalog_products(
            base_product,
            list(used_ids),
            limit - len(results)
        )
        results.extend(catalog_similar)
        used_ids.update(p["_id"] for p in catalog_similar)
    if len(results) < limit:
        random_products = await get_random_products(
            list(used_ids),
            limit - len(results)
        )
        results.extend(random_products)
    return results