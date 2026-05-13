from app.modules.carts import repository
from fastapi import HTTPException, status
from bson import ObjectId
from app.db.mongo import products_collection
from app.core import cache
from typing import Optional

def normalize_images(prod):
    imgs = []
    for img in prod.get("images") or []:
        img_copy = img.copy()
        if "_id" in img_copy:
            img_copy["_id"] = str(img_copy["_id"])
        imgs.append(img_copy)
    return imgs

def get_variant(product, selected_option: Optional[str]):
    variants = product.get("variants") or []
    if not variants:
        return None
    if not selected_option:
        return None
    for v in variants:
        if v["option"] == selected_option:
            return v
    return None

async def get_my_cart(user_id: str):
    cart = await repository.get_or_create_cart(user_id)
    product_ids = [ObjectId(item["product_id"]) for item in cart["items"]]
    products = []
    if product_ids:
        products = await products_collection.find(
            {"_id": {"$in": product_ids}}
        ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    total_raw = 0
    total_discounted = 0
    enriched_items = []
    removed_items = []
    for item in cart["items"]:
        product_id = item["product_id"]
        quantity = item["quantity"]
        product = cache.get_cached_product(product_id)
        if not product:
            product = product_map.get(product_id)
            if product:
                cache.set_cached_product(product_id, product)
        if not product:
            removed_items.append({
                "product_id": product_id,
                "name": None,
                "images": [],
                "reason": "not_found"
            })
            continue
        if product.get("is_blocked"):
            removed_items.append({
                "product_id": product_id,
                "name": product.get("name"),
                "images": normalize_images(product),
                "reason": "blocked"
            })
            continue
        if not product.get("is_active"):
            removed_items.append({
                "product_id": product_id,
                "name": product.get("name"),
                "images": normalize_images(product),
                "reason": "inactive"
            })
            continue
        selected_option = item.get("selected_option")
        variant = get_variant(product, selected_option)
        if product.get("variants"):
            if not variant:
                removed_items.append({
                    "product_id": product_id,
                    "name": product.get("name"),
                    "images": normalize_images(product),
                    "reason": "invalid_option"
                })
                continue
            available_stock = variant["stock"]
            price = variant["price"]
        else:
            available_stock = product.get("stock", 0)
            price = product.get("price", 0)
        if available_stock <= 0:
            removed_items.append({
                "product_id": product_id,
                "name": product.get("name"),
                "images": normalize_images(product),
                "reason": "out_of_stock"
            })
            continue
        if quantity > available_stock:
            removed_items.append({
                "product_id": product_id,
                "name": product.get("name"),
                "images": normalize_images(product),
                "reason": "insufficient_stock"
            })
            continue
        discount = product.get("discount", 0)
        subtotal_raw = price * quantity
        subtotal_discounted = price * (100 - discount) / 100 * quantity
        total_raw += subtotal_raw
        total_discounted += subtotal_discounted
        images = normalize_images(product)
        item_data = {
            "product_id": product_id,
            "quantity": quantity,
            "name": product["name"],
            "stock": available_stock,
            "images": images,
            "price": price,
            "discount": discount,
            "subtotal_raw": round(subtotal_raw, 2),
            "subtotal_discounted": round(subtotal_discounted, 2),
        }
        if selected_option:
            item_data["selected_option"] = selected_option
        enriched_items.append(item_data)
    if removed_items:
        await repository.remove_many_from_cart(
            cart["_id"],
            [item["product_id"] for item in removed_items]
        )
    return {
        "id": str(cart["_id"]),
        "items": enriched_items,
        "total_raw": round(total_raw, 2),
        "total_discounted": round(total_discounted, 2),
        "removed_items": removed_items
    }

async def add_item_to_cart(
    user_id: str,
    product_id: str,
    quantity: int,
    selected_option: Optional[str] = None
):
    product = await products_collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no existe"
        )
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cantidad inválida"
        )
    cart = await repository.get_or_create_cart(user_id)
    existing_qty = 0
    for item in cart.get("items", []):
        if item["product_id"] == product_id:
            if product.get("variants"):
                if item.get("selected_option") == selected_option:
                    existing_qty = item["quantity"]
                    break
            else:
                existing_qty = item["quantity"]
                break
    def get_variant(product, selected_option):
        variants = product.get("variants") or []
        if not variants or not selected_option:
            return None
        selected_option = selected_option.strip().lower()
        for v in variants:
            if v["option"].strip().lower() == selected_option:
                return v
        return None
    variant = get_variant(product, selected_option)
    if product.get("variants"):
        if not selected_option:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes elegir una variante"
            )
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Variante inválida"
            )
        available_stock = variant["stock"]
        price = variant["price"]
    else:
        available_stock = product.get("stock", 0)
        price = product.get("price", 0)
    if available_stock < existing_qty + quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo puedes pedir hasta {available_stock - existing_qty} cantidad"
        )
    cart["_id"] = str(cart["_id"])
    updated = await repository.add_or_update_item(
        cart_id=cart["_id"],
        product_id=product_id,
        quantity=quantity,
        price=price,
        selected_option=selected_option
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo actualizar el carrito"
        )
    return {"message": "Producto agregado al carrito correctamente"}

async def update_cart_item(user_id: str, product_id: str, quantity: int, selected_option: Optional[str] = None):
    cart = await repository.get_or_create_cart(user_id)
    cart["_id"] = str(cart["_id"])
    product = await products_collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no existe")
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cantidad inválida")
    variant = get_variant(product, selected_option)

    if product.get("variants"):
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Este producto no cuenta con variantes"
            )
        available_stock = variant["stock"]
    else:
        available_stock = product["stock"]
        if available_stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo puedes pedir hasta {available_stock} cantidad"
            )
    updated = await repository.update_item_quantity(
        cart_id=cart["_id"],
        product_id=product_id,
        quantity=quantity,
        selected_option=selected_option
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no está en el carrito")
    return {"message": "Cantidad actualizada correctamente"}

async def remove_cart_item(user_id: str, product_id: str, selected_option: Optional[str] = None):
    cart = await repository.get_or_create_cart(user_id)
    cart["_id"] = str(cart["_id"])
    removed = await repository.remove_item_from_cart(
        cart_id=cart["_id"],
        product_id=product_id,
        selected_option=selected_option
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado en el carrito")
    return {"message": "Producto eliminado del carrito"}

async def clear_cart(user_id: str):
    cart = await repository.get_or_create_cart(user_id)
    cart["_id"] = str(cart["_id"])
    cleared = await repository.clear_cart(cart_id=cart["_id"])
    if not cleared:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo vaciar el carrito")
    return {"message": "Carrito vaciado correctamente"}