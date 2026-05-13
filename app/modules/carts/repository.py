from app.db.mongo import carts_collection
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId

async def get_or_create_cart(user_id: str):
    cart = await carts_collection.find_one({"user_id": user_id})
    if cart:
        return cart
    cart = {
        "user_id": user_id,
        "items": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    result = await carts_collection.insert_one(cart)
    cart["_id"] = result.inserted_id
    return cart

async def add_or_update_item(
    cart_id,
    product_id: str,
    quantity: int,
    price: float,
    selected_option: str | None = None
):
    cart = await carts_collection.find_one({"_id": ObjectId(cart_id)})
    if not cart:
        return False
    for item in cart["items"]:
        if (
            item["product_id"] == product_id and
            item.get("selected_option") == selected_option
        ):
            new_qty = item["quantity"] + quantity
            result = await carts_collection.update_one(
                {
                    "_id": ObjectId(cart_id),
                    "items.product_id": product_id,
                    "items.selected_option": selected_option
                },
                {
                    "$set": {
                        "items.$.quantity": new_qty,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
    new_item = {
        "product_id": product_id,
        "quantity": quantity,
        "unit_price": price
    }
    if selected_option is not None:
        new_item["selected_option"] = selected_option
    result = await carts_collection.update_one(
        {"_id": ObjectId(cart_id)},
        {
            "$push": {
                "items": new_item
            },
            "$set": {
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0

async def update_item_quantity(cart_id, product_id: str, quantity: int,selected_option=None):
    filter_query = {
        "_id": ObjectId(cart_id),
        "items.product_id": product_id
    }
    if selected_option is not None:
        filter_query["items.selected_option"] = selected_option
    result = await carts_collection.update_one(
        filter_query,
        {
            "$set": {
                "items.$.quantity": quantity,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0

async def remove_item_from_cart(cart_id, product_id: str, selected_option: Optional[str] = None):
    pull_query = {"product_id": product_id}
    if selected_option is not None:
        pull_query["selected_option"] = selected_option
    result = await carts_collection.update_one(
        {"_id": ObjectId(cart_id)},
        {
            "$pull": {"items": pull_query},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    return result.modified_count > 0

async def remove_many_from_cart(cart_id, product_ids: list[str]):
    if not product_ids:
        return False
    result = await carts_collection.update_one(
        {"_id": ObjectId(cart_id)},
        {
            "$pull": {
                "items": {
                    "product_id": {"$in": product_ids}
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    return result.modified_count > 0

async def clear_cart(cart_id,session=None):
    result = await carts_collection.update_one(
        {"_id": ObjectId(cart_id)},
        {
            "$set": {
                "items": [],
                "updated_at": datetime.now(timezone.utc)
            }
        },
        session=session
    )
    return result.modified_count > 0