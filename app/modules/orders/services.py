from app.modules.carts import repository as carts_repository
from app.modules.orders import repository as orders_repository
from app.modules.auth import repository as auth_repository
from app.modules.users_control import repository as users_repository
from app.db.mongo import products_collection, client
from app.core.config import settings
from bson import ObjectId
from fastapi import HTTPException, status, Request
from datetime import datetime, timezone
from app.modules.contacts.send_email import send_order_client_email, send_order_staff_email, delivery_order_email, cancel_order_client_email, cancel_order_staff_email
from app.core.convert_date import convert_dates
import logging, math

logger = logging.getLogger(__name__)

class OrderActions:
    CREATE_ORDER = "CREATE_ORDER"
    UPDATE_ORDER = "UPDATE_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"



ALLOWED_TRANSITIONS = {
    "pending_payment": {"paid", "cancelled"},
    "paid": {"ready_pick_up"},
    "ready_pick_up": {"delivered"},
    "delivered": set(),
    "cancelled": set()
}
ALLOWED_ERASE_STATUSES = {"delivered", "cancelled"}

def status_traductor(my_status):
    if my_status=="pending_payment":
        return "esperando pago"
    elif my_status=="paid":
        return "pagado"
    elif my_status=="ready_pick_up":
        return "listo para recoger"
    else:
        return "cancelado"

async def enrich_order_items(order: dict) -> dict:
    product_ids = [ObjectId(item["product_id"]) for item in order["items"]]
    products = await products_collection.find(
        {"_id": {"$in": product_ids}}
    ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    for item in order["items"]:
        product = product_map.get(item["product_id"])
        if product:
            name = product["name"]
            if item.get("selected_option"):
                name += f" ({item['selected_option']})"
            item["name"] = name
            images = product.get("images") or []
            item["image"] = images[0]["url"] if images else None
        else:
            item["name"] = "Producto eliminado"
            item["image"] = None
    return order

def add_option_to_name(item: dict) -> str:
    name = item.get("name", "")
    option = item.get("selected_option")
    if option:
        return f"{name} ({option})"
    return name

async def create_order_guest(
    user_name: str,
    user_email: str,
    user_phone: str,
    items_input: list
):
    user_email = user_email.lower().strip()
    if not items_input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay productos en la orden")
    product_ids = [ObjectId(item["product_id"]) for item in items_input]
    products = await products_collection.find(
        {"_id": {"$in": product_ids}}
    ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    items = []
    total_raw = 0
    total_discounted = 0
    for item in items_input:
        product = product_map.get(item["product_id"])
        if not product:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un producto no existe")
        if not product.get("is_active", True) or product.get("is_blocked", False):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Producto no disponible: {product['name']}")
        quantity = item["quantity"]
        if not isinstance(quantity, int) or quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cantidad inválida")
        price = product.get("price") or 0
        discount = product.get("discount") or 0
        variants = product.get("variants") or []
        selected_option = item.get("selected_option")
        if variants:
            if not selected_option:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Debes elegir opción para {product['name']}"
                )
            variant = next(
                (v for v in variants if v.get("option") == selected_option),
                None
            )
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Opción inválida para {product['name']}"
                )
            stock = variant.get("stock")
            if stock is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock no definido para variante {selected_option}"
                )
        else:
            stock = product.get("stock") or 0
        stock = int(stock)
        if stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para {product['name']}"
            )
        subtotal_raw = price * quantity
        subtotal_discounted = price * (1 - discount / 100) * quantity
        total_raw += subtotal_raw
        total_discounted += subtotal_discounted
        items.append({
            "product_id": item["product_id"],
            "unit_price": price,
            "discount": discount,
            "quantity": quantity,
            "selected_option": selected_option,
            "subtotal_raw": round(subtotal_raw, 2),
            "subtotal_discounted": round(subtotal_discounted, 2)
        })
    async with await client.start_session() as session:
        async with session.start_transaction():
            for item in items_input:
                product = product_map[item["product_id"]]
                variants = product.get("variants") or []
                selected_option = item.get("selected_option")
                if variants:
                    variant_index = next(
                        (i for i, v in enumerate(variants)
                         if v.get("option") == selected_option),
                        None
                    )
                    if variant_index is None:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variante inválida")
                    result = await products_collection.update_one(
                        {
                            "_id": ObjectId(item["product_id"]),
                            f"variants.{variant_index}.stock": {"$gte": item["quantity"]},
                            "is_active": True,
                            "is_blocked": False
                        },
                        {
                            "$inc": {
                                f"variants.{variant_index}.stock": -item["quantity"],
                                "metrics.purchases": item["quantity"]
                            }
                        },
                        session=session
                    )
                else:
                    result = await products_collection.update_one(
                        {
                            "_id": ObjectId(item["product_id"]),
                            "stock": {"$gte": item["quantity"]},
                            "is_active": True,
                            "is_blocked": False
                        },
                        {
                            "$inc": {
                                "stock": -item["quantity"],
                                "metrics.purchases": item["quantity"]
                            }
                        },
                        session=session
                    )
                if result.modified_count == 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente para {product['name']}"
                    )
            order = await orders_repository.create_order(
                {
                    "user_id": None,
                    "guest_info": {
                        "name": user_name,
                        "email": user_email,
                        "phone": user_phone
                    },
                    "items": items,
                    "total_raw": round(total_raw, 2),
                    "total_discounted": round(total_discounted, 2),
                    "status": "pending_payment"
                },
                session=session
            )
    if not order:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creando la orden")
    order_out = order.copy()
    order_out["id"] = str(order_out["_id"])
    del order_out["_id"]
    order_out = await enrich_order_items(order_out)
    try:
        staff_emails = await auth_repository.get_staff_emails(settings.EMAIL_USER)
        await send_order_client_email(
            user_email=user_email,
            user_name=user_name,
            order=order_out
        )
        await send_order_staff_email(
            staff_emails=staff_emails,
            user_email=user_email,
            user_name=user_name,
            user_phone=user_phone,
            order=order_out
        )
    except Exception as e:
        logger.error(f"Order emails failed: {e}")
    return {
        "message": "Orden creada correctamente",
        "order": order_out
    }

async def checkout(
    role: str,
    user_id: str,
    user_name: str,
    user_phone: str,
    user_email: str,
    request: Request
):
    cart = await carts_repository.get_or_create_cart(user_id)
    if not cart.get("items"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Carrito vacío"
        )
    product_ids = [ObjectId(item["product_id"]) for item in cart["items"]]
    products = await products_collection.find(
        {"_id": {"$in": product_ids}}
    ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    items = []
    total_raw = 0
    total_discounted = 0
    for item in cart["items"]:
        product = product_map.get(item["product_id"])
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un producto ya no existe"
            )
        if not product.get("is_active", True) or product.get("is_blocked", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto no disponible: {product['name']}"
            )
        quantity = item["quantity"]
        selected_option = item.get("selected_option")
        variants = product.get("variants") or []
        if variants:
            variant = next(
                (v for v in variants if v.get("option") == selected_option),
                None
            )
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Variante inválida para {product['name']}"
                )
            stock = variant.get("stock") or 0
            price = variant.get("price") or 0
        else:
            stock = product.get("stock") or 0
            price = product.get("price") or 0
        if stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para {product['name']}"
            )
        discount = product.get("discount") or 0
        subtotal_raw = price * quantity
        subtotal_discounted = price * (1 - discount / 100) * quantity
        total_raw += subtotal_raw
        total_discounted += subtotal_discounted
        items.append({
            "product_id": item["product_id"],
            "unit_price": price,
            "discount": discount,
            "quantity": quantity,
            "selected_option": selected_option,
            "subtotal_raw": round(subtotal_raw, 2),
            "subtotal_discounted": round(subtotal_discounted, 2)
        })
    async with await client.start_session() as session:
        async with session.start_transaction():
            for item in cart["items"]:
                product = product_map[item["product_id"]]
                selected_option = item.get("selected_option")
                variants = product.get("variants") or []
                if variants:
                    idx = next(
                        (i for i, v in enumerate(variants)
                         if v.get("option") == selected_option),
                        None
                    )
                    if idx is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Variante inválida"
                        )
                    result = await products_collection.update_one(
                        {
                            "_id": ObjectId(item["product_id"]),
                            f"variants.{idx}.stock": {"$gte": item["quantity"]},
                            "is_active": True,
                            "is_blocked": False
                        },
                        {
                            "$inc": {
                                f"variants.{idx}.stock": -item["quantity"],
                                "metrics.purchases": item["quantity"]
                            }
                        },
                        session=session
                    )
                else:
                    result = await products_collection.update_one(
                        {
                            "_id": ObjectId(item["product_id"]),
                            "stock": {"$gte": item["quantity"]},
                            "is_active": True,
                            "is_blocked": False
                        },
                        {
                            "$inc": {
                                "stock": -item["quantity"],
                                "metrics.purchases": item["quantity"]
                            }
                        },
                        session=session
                    )
                if result.modified_count == 0:
                    print(product)
                    print(result)
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente para {product['name']}"
                    )
            order = await orders_repository.create_order(
                {
                    "user_id": user_id,
                    "items": items,
                    "total_raw": round(total_raw, 2),
                    "total_discounted": round(total_discounted, 2),
                    "status": "pending_payment"
                },
                session=session
            )
            await carts_repository.clear_cart(str(cart["_id"]), session=session)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creando la orden"
        )
    order_out = order.copy()
    order_out["id"] = str(order_out["_id"])
    del order_out["_id"]
    order_out = await enrich_order_items(order_out)
    for item in order_out["items"]:
        if item.get("selected_option"):
            item["name"] = f"{item['name']} ({item['selected_option']})"
    try:
        await users_repository.add_user_history(
            email=user_email,
            action=OrderActions.CREATE_ORDER,
            message=f"Creó la orden {order_out['code']}",
            request=request,
            role=role,
            entity="order",
            entity_id=order_out["code"],
            now=datetime.now(timezone.utc),
            extra={
                "total_raw": order_out["total_raw"],
                "total_discounted": order_out["total_discounted"],
                "items_count": len(order_out["items"]),
                "products": [i["product_id"] for i in order_out["items"]]
            }
        )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")
    try:
        staff_emails = await auth_repository.get_staff_emails(settings.EMAIL_USER)
        await send_order_client_email(
            user_email=user_email,
            user_name=user_name,
            order=order_out
        )
        await send_order_staff_email(
            staff_emails=staff_emails,
            user_email=user_email,
            user_name=user_name,
            user_phone=user_phone,
            order=order_out
        )
    except Exception as e:
        logger.error(f"Order emails failed: {e}")
    return {
        "message": "Orden creada correctamente",
        "order": order_out
    }

async def get_order(user_id: str, code: str, role: str, request:Request):
    order = await orders_repository.get_order_by_code(code)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    order = await enrich_order_items(order)
    if "history" in order and isinstance(order["history"], list):
        order["history"].sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
    order["id"] = str(order["_id"])
    del order["_id"]
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    user_is_staff = (role == "admin" or role == "moderator")
    user_is_owner = order["user_id"] == user_id
    if not (user_is_staff or user_is_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    order = convert_dates(order, request.state.tz)
    return order

async def get_my_orders(user_id: str, request:Request, page: int = 0):
    result = await orders_repository.get_orders_history(
        user_id=user_id,
        page=page
    )
    orders = result["orders"]
    pagination = result["pagination"]
    all_product_ids = set()
    for order in orders:
        for item in order["items"]:
            all_product_ids.add(ObjectId(item["product_id"]))
    products = await products_collection.find(
        {"_id": {"$in": list(all_product_ids)}}
    ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    for order in orders:
        order["id"] = str(order["_id"])
        del order["_id"]
        for item in order["items"]:
            product = product_map.get(item["product_id"])
            if product:
                name = product["name"]
                if item.get("selected_option"):
                    name += f" ({item['selected_option']})"
                item["name"] = name
                images = product.get("images") or []
                item["image"] = images[0]["url"] if images else None
            else:
                item["name"] = "Producto eliminado"
                item["image"] = None
    result = {
        "orders": orders,
        "pagination": pagination
    }
    return convert_dates(result, request.state.tz)

async def update_order_status(role: str, email: str,code: str, new_status: str, request:Request): 
    order=await orders_repository.get_order_by_code(code)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    allowed = ALLOWED_TRANSITIONS.get(order["status"], set())
    if new_status not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado inválido")
    result = await orders_repository.update_order_status_transition(
        code=code,
        status=new_status,
        by=email
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada") 
    try:
        await users_repository.add_user_history(
            email=email,
            action=OrderActions.UPDATE_ORDER,
            message=f"Cambió estado de la orden {code} a {status_traductor(new_status)}",
            request=request,
            role=role,
            entity="order",
            entity_id=code,
            now=datetime.now(timezone.utc),
            extra={
                "old_status": order["status"],
                "new_status": new_status
            }
        )
    except Exception as e:
        logger.error(f"Audit log failed for order {order['code']}: {e}")
    if new_status=="delivered":
        try:
            client_id=order["user_id"]
            user=await auth_repository.get_user_by_id(client_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
            updated = await orders_repository.get_order_by_code(code)
            updated = await enrich_order_items(updated)
            updated["id"] = str(updated["_id"])
            del updated["_id"]
            await delivery_order_email(
                user_email=user["email"],
                user_name=user["name"],
                order=updated
            )
        except Exception as e:
            logger.error(f"Order emails failed: {e}")
    return {"message": f"Estado actualizado a {new_status}"}

async def cancel_order(role: str, email: str, code: str, user_id: str, request: Request):
    order = await orders_repository.get_order(user_id, code)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    if order["status"] not in {"pending_payment", "paid"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya no se puede cancelar la orden"
        )
    not_restored = []
    async with await client.start_session() as session:
        async with session.start_transaction():
            for item in order["items"]:
                product = await products_collection.find_one(
                    {"_id": ObjectId(item["product_id"])},
                    session=session
                )
                if not product or not product.get("is_active", True) or product.get("is_blocked", False):
                    not_restored.append({
                        "product_id": item["product_id"],
                        "name": item.get("name"),
                        "reason": "removed_or_inactive"
                    })
                    continue
                variants = product.get("variants") or []
                selected_option = item.get("selected_option")
                if variants:
                    idx = next(
                        (i for i, v in enumerate(variants)
                         if v.get("option") == selected_option),
                        None
                    )
                    if idx is None:
                        not_restored.append({
                            "product_id": item["product_id"],
                            "name": item.get("name"),
                            "reason": "variant_not_found"
                        })
                        continue
                    current_stock = variants[idx].get("stock")
                    if current_stock is None:
                        await products_collection.update_one(
                            {"_id": product["_id"]},
                            {"$set": {f"variants.{idx}.stock": 0}},
                            session=session
                        )
                    await products_collection.update_one(
                        {"_id": product["_id"]},
                        {
                            "$inc": {
                                f"variants.{idx}.stock": item["quantity"]
                            }
                        },
                        session=session
                    )
                else:
                    current_stock = product.get("stock")
                    if current_stock is None:
                        await products_collection.update_one(
                            {"_id": product["_id"]},
                            {"$set": {"stock": 0}},
                            session=session
                        )
                    await products_collection.update_one(
                        {"_id": product["_id"]},
                        {
                            "$inc": {
                                "stock": item["quantity"]
                            }
                        },
                        session=session
                    )
            await orders_repository.update_order_status_transition(
                code=code,
                status="cancelled",
                by=email
            )
    try:
        await users_repository.add_user_history(
            email=email,
            action=OrderActions.CANCEL_ORDER,
            message=f"Canceló la orden {code}",
            request=request,
            role=role,
            entity="order",
            entity_id=code,
            now=datetime.now(timezone.utc),
            extra={
                "previous_status": order["status"]
            }
        )
    except Exception as e:
        logger.error(f"Audit log failed for order {order.get('id')}: {e}")
    try:
        user = await auth_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        staff_emails = await auth_repository.get_staff_emails(settings.EMAIL_USER)
        updated = await orders_repository.get_order_by_code(code)
        updated["id"] = str(updated["_id"])
        del updated["_id"]
        await cancel_order_client_email(
            user_email=user["email"],
            user_name=user["name"],
            order=updated
        )
        await cancel_order_staff_email(
            staff_emails=staff_emails,
            user_name=user["name"],
            order=updated
        )
    except Exception as e:
        logger.error(f"Order emails failed: {e}")
    return {
        "message": "Pedido cancelado correctamente",
        "not_restored": not_restored
    }

async def get_orders(
    page: int,
    page_size: int,
    request: Request,
    email_user: str | None = None,
    code: str | None = None,
    erased: str = "normal"
):
    match_stage = {}
    if code:
        match_stage["code"] = code.upper()
    if erased == "normal":
        match_stage["is_erased"] = {"$ne": True}
    if erased == "erased":
        match_stage["is_erased"] = True
    base_pipeline = [
        {"$match": match_stage},
        {
            "$addFields": {
                "user_id_obj": {
                    "$convert": {
                        "input": "$user_id",
                        "to": "objectId",
                        "onError": None,
                        "onNull": None
                    }
                }
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id_obj",
                "foreignField": "_id",
                "as": "user_data"
            }
        },
        {
            "$unwind": {
                "path": "$user_data",
                "preserveNullAndEmptyArrays": True
            }
        }
    ]
    if email_user:
        base_pipeline.append({
            "$match": {
                "$or": [
                    {"user_data.email": email_user},
                    {"guest_info.email": email_user}
                ]
            }
        })
    count_pipeline = base_pipeline + [{"$count": "total"}]
    count_cursor = orders_repository.aggregate(count_pipeline)
    count_result = await count_cursor.to_list(length=1)
    total_orders = count_result[0]["total"] if count_result else 0
    total_pages = math.ceil(total_orders / page_size) if page_size else 1
    pipeline = base_pipeline + [
        {
            "$project": {
                "code": 1,
                "status": 1,
                "total_raw": 1,
                "total_discounted": 1,
                "created_at": 1,
                "is_erased": 1,
                "items": 1,
                "email": {
                    "$ifNull": ["$user_data.email", "$guest_info.email"]
                },
                "user_name": {
                    "$ifNull": ["$user_data.name", "$guest_info.name"]
                }
            }
        },
        {"$sort": {"created_at": -1}},
        {"$skip": page * page_size},
        {"$limit": page_size}
    ]
    cursor = orders_repository.aggregate(pipeline)
    orders = await cursor.to_list(length=page_size)
    all_product_ids = set()
    for order in orders:
        for item in order["items"]:
            all_product_ids.add(ObjectId(item["product_id"]))
    products = await products_collection.find(
        {"_id": {"$in": list(all_product_ids)}}
    ).to_list(None)
    product_map = {str(p["_id"]): p for p in products}
    for order in orders:
        order["id"] = str(order["_id"])
        del order["_id"]
        for item in order["items"]:
            product = product_map.get(item["product_id"])
            if product:
                name = product["name"]
                if item.get("selected_option"):
                    name += f" ({item['selected_option']})"
                item["name"] = name
                images = product.get("images") or []
                item["image"] = images[0]["url"] if images else None
            else:
                item["name"] = "Producto eliminado"
                item["image"] = None
    result = {
        "orders": orders,
        "pagination": {
            "total_pages": total_pages,
            "total_orders": total_orders,
            "page_size": page_size
        }
    }
    return convert_dates(result, request.state.tz)

async def restore_order(code: str, email: str):
    ok = await orders_repository.restore_order(
        code=code,
        by=email
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    return {"message": "Orden restaurada"}

async def erase_order(code: str, user_id: str, user_email: str):
    order = await orders_repository.get_order_by_code(code)
    if not order or order["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    if order["status"] not in ALLOWED_ERASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden eliminar órdenes entregadas o canceladas"
        )
    ok = await orders_repository.erase_order(
        code=code,
        user_id=user_id,
        user_email=user_email
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    return {"message": "Orden eliminada"}