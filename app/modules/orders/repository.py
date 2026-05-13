from app.db.mongo import orders_collection, counters_collection
from bson import ObjectId
from datetime import datetime, timezone
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
import math

async def add_order_status_transition(
    code: str,
    status: str,
    by: str,
    session=None
):
    event = {
        "status": status,
        "by": by,
        "timestamp": datetime.now(timezone.utc)
    }
    await orders_collection.update_one(
        {"code": code.upper()},
        {
            "$set": {
                "status": status,
                "updated_at": event["timestamp"]
            },
            "$push": {
                "history": event
            }
        },
        session=session
    )

async def get_next_sequence(name: str):
    result = await counters_collection.find_one_and_update(
        {"_id": name},
        {"$setOnInsert": {"type":"order"},
        "$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return result.get("seq", 1)

async def generate_order_code(now:datetime):
    year = now.year
    seq = await get_next_sequence(f"orders_{year}")
    return f"ORD-{year}-{str(seq).zfill(6)}"

async def create_order(order: dict, session=None):
    try:
        now = datetime.now(timezone.utc)
        order["is_erased"] = False
        order["code"] = (await generate_order_code(now)).upper()
        order["created_at"] = now
        order["status"] = "pending_payment"
        order["history"] = [
            {
                "status": "pending_payment",
                "by": "system",
                "timestamp": now
            }
        ]
        result = await orders_collection.insert_one(order, session=session)
        order["_id"] = result.inserted_id
        return order
    except PyMongoError as e:
        print(f"Error creando orden: {e}")
        return None

async def get_orders_history(user_id: str, page: int = 0):
    PAGE_SIZE = 8
    if page < 0:
        page = 0
    query = {
        "user_id": user_id,
        "is_erased": {"$ne": True}
    }
    total_orders = await orders_collection.count_documents(query)
    cursor = (
        orders_collection.find(query)
        .sort("created_at", -1)
        .skip(page * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    orders = await cursor.to_list(length=PAGE_SIZE)
    return {
        "orders": orders,
        "pagination": {
            "total_orders": total_orders,
            "returned": len(orders),
            "page": page,
            "page_size": PAGE_SIZE,
            "total_pages": (total_orders + PAGE_SIZE - 1) // PAGE_SIZE
        }
    }

async def get_order_by_id(order_id: str):
    order = await orders_collection.find_one(
        {
            "_id": ObjectId(order_id),
            "is_erased": {"$ne": True}
        }
    )
    return order

async def get_order_by_code(code: str):
    order = await orders_collection.find_one(
        {
            "code": code.upper(),
            "is_erased": {"$ne": True}
        }
    )
    return order

async def update_order_status_transition(
    code: str,
    status: str,
    by: str = "system",
    session=None
):
    now = datetime.now(timezone.utc)
    return await orders_collection.update_one(
        {"code": code.upper()},
        {
            "$set": {
                "status": status,
                "updated_at": now
            },
            "$push": {
                "history": {
                    "status": status,
                    "by": by,
                    "timestamp": now
                }
            }
        },
        session=session
    )

async def erase_order(code: str, user_id: str, user_email:str, session=None):
    now = datetime.now(timezone.utc)
    return await orders_collection.update_one(
        {
            "code": code.upper(),
            "user_id": user_id,
            "is_erased": {"$ne": True}
        },
        {
            "$set": {
                "is_erased": True,
                "erased_at": now,
                "updated_at": now
            },
            "$push": {
                "history": {
                    "status": "erased",
                    "by": user_email,
                    "timestamp": now
                }
            }
        },
        session=session
    )

async def restore_order(code: str, by: str, session=None):
    now = datetime.now(timezone.utc)
    return await orders_collection.update_one(
        {
            "code": code.upper(),
            "is_erased": True
        },
        {
            "$set": {
                "is_erased": False,
                "updated_at": now,
                "status": "pending_payment"
            },
            "$unset": {
                "erased_at": ""
            },
            "$push": {
                "history": {
                    "status": "restored",
                    "by": by,
                    "timestamp": now
                }
            }
        },
        session=session
    )

async def get_order(user_id: str, code: str) -> dict | None:
    doc = await orders_collection.find_one(
        {
            "code": code.upper(),
            "user_id": user_id,
            "is_erased": {"$ne": True}
        }
    )
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc

async def get_orders(
    page: int = 0,
    page_size: int = 8,
    user_id: str | None = None,
    order_id: str | None = None,
    code: str | None = None,
    erased: str = "all"
):
    query = {}
    if erased == "normal":
        query["is_erased"] = {"$ne": True}
    elif erased == "erased":
        query["is_erased"] = True
    if order_id:
        query["_id"] = ObjectId(order_id)
    if code:
        query["code"] = code.upper()
    if user_id:
        query["user_id"] = user_id
    total_orders = await orders_collection.count_documents(query)
    total_pages = max(1, math.ceil(total_orders / page_size))
    page = max(0, min(page, total_pages))
    skip = (page) * page_size
    cursor = (
        orders_collection
        .find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    orders = await cursor.to_list(length=page_size)
    return {
        "orders": orders,
        "pagination": {
            "total_orders": total_orders,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size
        }
    }

def aggregate(pipeline):
    cursor = orders_collection.aggregate(pipeline)
    return cursor

async def attach_orders_to_user(user_id: str, email: str):
    result = await orders_collection.update_many(
        {
            "user_id": None,
            "guest_info.email": email.lower().strip()
        },
        {
            "$set": {
                "user_id": user_id
            },
            "$unset": {
                "guest_info": ""
            }
        }
    )
    return result.modified_count

async def exists_guest_orders(email: str) -> bool:
    order = await orders_collection.find_one(
        {
            "user_id": None,
            "guest_info.email": email.lower().strip()
        },
        {"_id": 1}
    )
    return order is not None