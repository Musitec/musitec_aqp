from app import cloudinary
from app.modules.products_control import repository as products_repository
from app.modules.users_control import repository as users_repository
from app.core.convert_date import convert_dates
from fastapi import UploadFile, HTTPException, status, Request, Form, File
from typing import Optional,List,Union
import json, math, copy
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from PIL import Image
from app.modules.products_control.schemas import StockChangeItem
from io import BytesIO
from app.modules.products.utils import apply_discount_logic
from zoneinfo import ZoneInfo

PERU_TZ = ZoneInfo("America/Lima")


class AdminActions:
    CREATE_PRODUCT = "CREATE_PRODUCT"
    UPDATE_PRODUCT = "UPDATE_PRODUCT"
    ACTIVATE_PRODUCT = "ACTIVATE_PRODUCT"
    DEACTIVATE_PRODUCT = "DEACTIVATE_PRODUCT"
    BLOCK_PRODUCT = "BLOCK_PRODUCT"
    UNBLOCK_PRODUCT = "UNBLOCK_PRODUCT"
    UPDATE_STOCK = "UPDATE_STOCK"
    UPDATE_DISCOUNT = "UPDATE_DISCOUNT"
    REMOVE_DISCOUNT = "REMOVE_DISCOUNT"

MAX_SIZE = 5 * 1024 * 1024

IGNORED_FIELDS = {
    "_id", "updatedAt", "changeLog", "stockHistory"
}

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/webp"
}

def serialize_mongo(doc):
    if isinstance(doc, list):
        return [serialize_mongo(i) for i in doc]
    if isinstance(doc, dict):
        return {k: serialize_mongo(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc

async def validate_images(files: List[UploadFile]):
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archivo no permitido: {file.filename}"
            )
        contents = await file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{file.filename} supera el tamaño máximo de 5MB"
            )
        try:
            img = Image.open(BytesIO(contents))
            img.verify()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{file.filename} no es una imagen válida"
            )
        file.file.seek(0)

def compute_set_diff(original: dict, updated: dict) -> dict:
    set_data = {}
    for key, value in updated.items():
        if key in ("_id", "images"):
            continue
        if serialize_mongo(original.get(key)) != serialize_mongo(value):
            set_data[key] = value
    return set_data

def build_change_log(old, new, now, user_email=None):
    logs = []
    all_keys = set(old.keys()) | set(new.keys())
    for key in all_keys:
        if key in IGNORED_FIELDS:
            continue
        if old.get(key) != new.get(key):
            logs.append({
                "field": key,
                "old": old.get(key),
                "new": new.get(key),
                "created_at": now,
                "user_email": user_email
            })
    return logs

async def get_product_or_404(product_id: str):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de producto inválido")
    product = await products_repository.find_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product

def apply_basic_updates(product, name, description, catalog, price, stock):
    if price is not None and price < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El precio no puede ser negativo")
    if name:
        product["name"] = name
    if description is not None:
        product["description"] = description
    if catalog:
        product["catalog"] = catalog
    if price is not None:
        product["price"] = price
    if stock is not None:
        product["stock"] = stock

def update_specifications(product, specifications):
    if specifications is not None:
        try:
            new_specs = json.loads(specifications)
            if has_empty_object(new_specs):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="specifications contiene objetos JSON vacíos"
                )
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de especificaciones inválido"
            )
        if not isinstance(new_specs, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Las especificaciones deben ser un objeto"
            )
        product["specifications"] = new_specs

def no_duplicate_keys(pairs):
    result = {}
    seen = set()
    for key, value in pairs:
        normalized = key.lower()
        if normalized in seen:
            raise ValueError(f"Clave duplicada en specifications: {key}")
        seen.add(normalized)
        result[key] = value
    return result

def has_empty_object(specs: dict) -> bool:
    for key, value in specs.items():
        if isinstance(value, dict):
            if len(value) == 0:
                return True
            if has_empty_object(value):
                return True
    return False

async def handle_images(product, removeImages, files, replaceImages, tempIds):
    MAX_IMAGES = 5
    current_images = product.get("images", [])
    remove_set = set(removeImages) if removeImages else set()
    valid_public_ids = {img["public_id"] for img in current_images}
    remove_set = remove_set & valid_public_ids
    images_to_delete = [
        img for img in current_images
        if img["public_id"] in remove_set
    ]
    remaining_images = [
        img for img in current_images
        if img["public_id"] not in remove_set
    ]
    upload_count = len(files or [])
    final_count = upload_count if replaceImages else len(remaining_images) + upload_count
    if final_count > MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Máximo {MAX_IMAGES} imágenes"
        )
    if final_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe haber al menos una imagen"
        )
    uploaded_images = []
    temp_to_public = {}
    if files:
        if not tempIds or len(files) != len(tempIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tempIds inválidos o faltantes"
            )
        if len(set(tempIds)) != len(tempIds):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tempIds duplicados"
            )
        await validate_images(files)
        uploads = await cloudinary.upload_to_cloudinary(files)
        if len(uploads) != len(files):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error subiendo imágenes"
            )
        for i, uploaded in enumerate(uploads):
            if not uploaded.get("public_id") or not uploaded.get("url"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Imagen inválida"
                )
            public_id = uploaded["public_id"]
            temp_id = tempIds[i]
            temp_to_public[temp_id] = public_id
            uploaded_images.append({
                "url": uploaded["url"],
                "public_id": public_id
            })
    if replaceImages:
        images_to_delete.extend(remaining_images)
        final_images = uploaded_images
    else:
        final_images = remaining_images + uploaded_images
    return images_to_delete, final_images, temp_to_public, uploaded_images

async def create_product(
    user_id: str,
    email: str,
    role: str,
    files: list[UploadFile],
    product_name: str,
    specifications: str,
    description: Optional[str],
    catalog: str,
    request: Request,
    price: Optional[float]=None,
    stock: Optional[str]=None,
    variants: Optional[str] = None
):
    if variants and (price is not None or stock is not None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes enviar price o stock si usas variants"
        )
    if variants:
        try:
            variants = json.loads(variants)
            if not isinstance(variants, list) or len(variants) == 0:
                raise ValueError()
            clean_variants = []
            seen = set()
            for v in variants:
                if not isinstance(v, dict):
                    raise ValueError()
                option = v.get("option")
                stock_v = v.get("stock")
                price_v = v.get("price")
                if not option or not isinstance(option, str):
                    raise ValueError()
                key = option.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                if not isinstance(stock_v, int) or stock_v < 0:
                    raise ValueError()
                if not isinstance(price_v, (int, float)) or price_v < 0:
                    raise ValueError()
                clean_variants.append({
                    "option": option.strip(),
                    "stock": stock_v,
                    "price": price_v
                })
            clean_variants.sort(key=lambda x: x["price"])
            variants = clean_variants
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="variants inválido"
            )
    else:
        variants = None
        if stock is None or price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes enviar price y stock si no usas variants"
            )
        try:
            stock = int(stock)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stock debe ser un número"
            )
        if stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stock no puede ser negativo"
            )
        if price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="price no puede ser negativo"
            )
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo 5 imágenes por producto"
        )
    await validate_images(files)
    specs = {}
    if specifications and specifications.strip():
        try:
            specs = json.loads(specifications, object_pairs_hook=no_duplicate_keys)
            if not isinstance(specs, dict):
                raise ValueError()
            if has_empty_object(specs):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="specifications contiene objetos JSON vacíos"
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e) or "specifications debe ser un JSON válido"
            )
    now = datetime.now(timezone.utc)
    images = []
    product_id = None
    try:
        images = await cloudinary.upload_to_cloudinary(files)
        product_id = await products_repository.create_product(
            images=images,
            product_name=product_name,
            specifications=specs,
            description=description,
            price=price,
            stock=stock,
            now=now,
            user=email,
            catalog=catalog,
            variants=variants
        )
        if product_id is None:
            raise Exception("No se pudo guardar el producto")
        await users_repository.add_user_history(
            email=email,
            action=AdminActions.CREATE_PRODUCT,
            message=f"Creó el producto '{product_name}'",
            request=request,
            role=role,
            entity="product",
            entity_id=str(product_id),
            now=now,
            extra={
                "price": price,
                "stock": stock
            }
        )
    except Exception as e:
        if product_id:
            await products_repository.delete_hard_product(product_id)
        for image in images:
            try:
                await cloudinary.delete_from_cloudinary(image["public_id"])
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando producto. Operación revertida: {str(e)}"
        )
    return {
        "message": "Producto creado correctamente",
        "product_id": product_id
    }
    
async def update_product(
    request: Request,
    product_id: str,
    email: str,
    role: str,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    catalog: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    stock: Optional[str] = Form(None),
    specifications: Optional[str] = Form(None),
    removeImages: Optional[List[str]] = Form(None),
    replaceImages: Optional[bool] = Form(False),
    files: Optional[List[UploadFile]] = File(None),
    variants: Optional[str] = Form(None),
    tempIds: Optional[List[str]] = Form(None),
    imageOrder: Optional[str] = Form(None)
):
    print("VARIANTS:", variants)
    print("PRICE:", price)
    print("STOCK:", stock)
    if variants is not None and len(variants.strip()) > 0:
        if price is not None or stock is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes enviar stock o price junto con variants"
            )
    product_db = await get_product_or_404(product_id)
    original_product = copy.deepcopy(product_db)
    product = copy.deepcopy(product_db)
    if variants is not None:
        try:
            variants = json.loads(variants)
            if not isinstance(variants, list):
                raise ValueError()
            clean_variants = []
            seen = set()
            for v in variants:
                if not isinstance(v, dict):
                    raise ValueError()
                option = v.get("option")
                stock_v = v.get("stock")
                price_v = v.get("price")
                if not option or not isinstance(option, str):
                    raise ValueError()
                key = option.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                clean_variants.append({
                    "option": option.strip(),
                    "stock": stock_v,
                    "price": price_v
                })
            if len(clean_variants) > 0:
                product["variants"] = clean_variants
                product["price"] = None
                product["stock"] = None
            else:
                if price is None or stock is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Si eliminas todas las variantes debes enviar price y stock"
                    )
                product.pop("variants", None)
                product["price"] = price
                product["stock"] = int(stock)
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="variants inválido"
            )
    else:
        if price is None and stock is None and "variants" not in product_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes mantener price y stock si no usas variants"
            )
        if price is not None:
            if price < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="price no puede ser negativo"
                )
            product["price"] = price
        if stock is not None:
            try:
                stock = int(stock)
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="stock debe ser un número"
                )
            if stock < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="stock no puede ser negativo"
                )
            product["stock"] = stock
        product.pop("variants", None)
        apply_basic_updates(
            product=product,
            name=name,
            description=description,
            catalog=catalog,
            price=price,
            stock=stock
        )
    update_specifications(
        product=product,
        specifications=specifications
    )
    remove_images_list = []
    if removeImages:
        try:
            remove_images_list = json.loads(removeImages)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato removeImages inválido"
            )
    uploaded_images = []
    images_to_delete = []
    files = files or []
    try:
        images_to_delete, final_images, temp_to_public, uploaded_images = await handle_images(
            product,
            remove_images_list,
            files,
            replaceImages,
            tempIds=tempIds
        )
        if imageOrder:
            try:
                order = json.loads(imageOrder)
                if not isinstance(order, list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="imageOrder debe ser un array"
                    )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Formato imageOrder inválido"
                )
            order = [temp_to_public.get(i, i) for i in order]
            id_map = {img["public_id"]: img for img in final_images}
            if len(order) != len(set(order)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="imageOrder duplicado"
                )
            ordered_images = [id_map[i] for i in order if i in id_map]
            remaining = [img for img in final_images if img["public_id"] not in order]
            product["images"] = ordered_images + remaining
        else:
            product["images"] = final_images
        now = datetime.now(timezone.utc)
        product["updatedAt"] = now
        change_logs = build_change_log(original_product, product, now, email)
        parts = []
        parts.append(product.get("name", "") or "")
        parts.append(product.get("description", "") or "")
        parts.append(product.get("catalog", "") or "")

        specs = product.get("specifications", {})
        if isinstance(specs, dict):
            for k, v in specs.items():
                parts.append(str(k))
                parts.append(str(v))
        variants_data = product.get("variants", [])
        if isinstance(variants_data, list):
            for v in variants_data:
                parts.append(str(v.get("option", "")))
        product["search_blob"] = " ".join(parts).lower()
        product_to_update = product.copy()
        product_to_update.pop("_id", None)
        set_data = compute_set_diff(original_product, product_to_update)
        update_data = {}
        if set_data:
            update_data["$set"] = set_data
        clean_images = []
        for img in product["images"]:
            img_copy = img.copy()
            img_copy.pop("_id", None)
            img_copy.pop("tempId", None)
            clean_images.append(img_copy)
        update_data["$set"]["images"] = clean_images
        if change_logs:
            update_data["$push"] = {"changeLog": {"$each": change_logs}}
        if update_data:
            await products_repository.update_product(
                product_id=product_id,
                data=update_data
            )
        for img in images_to_delete:
            try:
                await cloudinary.delete_from_cloudinary(img["public_id"])
            except Exception:
                pass
    except Exception as e:
        for img in uploaded_images:
            try:
                await cloudinary.delete_from_cloudinary(img["public_id"])
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando producto. Operación revertida: {str(e)}"
        )
    try:
        await users_repository.add_user_history(
            email=email,
            action=AdminActions.UPDATE_PRODUCT,
            message=f"Actualizó el producto {product['name']}",
            request=request,
            role=role,
            entity="product",
            entity_id=str(product_id),
            now=now,
            extra={
                "changes": change_logs
            }
        )
    except Exception:
        pass
    return {
        "message": "Producto actualizado correctamente"
    }

async def create_discount(
    role: str,
    email: str,
    user_id: str,
    product_id: str,
    discount: int,
    days: int,
    hours: int,
    minutes: int,
    request: Request
):
    if discount <= 0 or discount > 40:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valor de descuento inadecuado"
        )
    if days < 0 or days > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los días deben estar entre 0 y 7"
        )
    if hours < 0 or hours > 23:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las horas deben estar entre 0 y 23"
        )
    if minutes < 0 or minutes > 59:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los minutos deben estar entre 0 y 59"
        )
    now = datetime.now(timezone.utc)
    delta = timedelta(days=days, hours=hours, minutes=minutes)
    stopDiscount = now + delta
    if delta.total_seconds() <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tiempo del descuento debe ser mayor a 0"
        )
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    if product_db.get("is_active")==False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes aplicar descuentos a productos desactivados"
        )
    if product_db.get("is_blocked")==True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes aplicar descuentos a productos bloqueados"
        )
    result = await products_repository.create_discount(
        product_id=product_id,
        discount=discount,
        now=now,
        stopDiscount=stopDiscount
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al aplicar descuento"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio (el descuento ya estaba activo)"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.UPDATE_DISCOUNT,
        message=f"Aplicó descuento de {discount}% al producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now,
        extra={
            "expires_in": f"{days}d {hours}h {minutes}m"
        }
    )
    return {
        "message": "Descuento aplicado correctamente",
    }

async def change_stock(
    role: str,
    user_id: str,
    email: str,
    product_id: str,
    stock: Union[int, List[StockChangeItem]],
    request: Request,
):
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    now = datetime.now(timezone.utc)
    if "variants" in product_db and product_db["variants"]:
        if not isinstance(stock, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El stock debe ser un array para productos con variantes"
            )
        current_variants = product_db["variants"]
        new_variants = []
        for variant in current_variants:
            option = variant["option"]
            change = next((s for s in stock if s.option == option), None)
            delta = change.delta if change else 0
            new_value = int(variant["stock"]) + delta
            if new_value < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuficiente en variante {option}"
                )
            updated_variant = variant.copy()
            updated_variant["stock"] = new_value
            new_variants.append(updated_variant)
        result = await products_repository.update_stock_variants(
            product_id=product_id,
            new_variants=new_variants,
            now=now
        )    
        new_stock_response = new_variants
    else:
        current_stock = product_db.get("stock")
        if not isinstance(current_stock, int):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Formato de stock inválido"
            )
        if not isinstance(stock, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El stock debe ser un número"
            )
        new_stock = current_stock + stock
        if new_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stock insuficiente"
            )
        result = await products_repository.update_stock_simple(
            product_id=product_id,
            new_stock=new_stock,
            now=now
        )
        new_stock_response = new_stock
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al modificar el stock"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.UPDATE_STOCK,
        message=f"Actualizó el stock del producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now,
        extra={
            "new_stock": new_stock_response
        }
    )
    return {
        "message": "Stock actualizado",
        "stock": new_stock_response
    }

async def block_product(role: str, user_id:str, email: str, product_id:str, request:Request):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    now=datetime.now(timezone.utc)
    result = await products_repository.block_product(
        product_id=product_id,
        now=now
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al modificar el stock"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.BLOCK_PRODUCT,
        message=f"Bloqueó el producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now
    )
    return {"message": "Producto bloqueado"}

async def unblock_product(role: str, user_id:str, email: str, product_id:str, request:Request):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    now=datetime.now(timezone.utc)
    result = await products_repository.unblock_product(
        product_id=product_id,
        now=now
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al modificar el stock"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.UNBLOCK_PRODUCT,
        message=f"Desbloqueó el producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now
    )
    return {"message": "Producto desbloqueado"}

async def deactivate_product(role: str, user_id:str, email: str, product_id:str, request:Request):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    now=datetime.now(timezone.utc)
    result = await products_repository.deactivate_product(
        product_id=product_id,
        now=now
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al modificar el stock"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.DEACTIVATE_PRODUCT,
        message=f"Desactivó el producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now
    )
    return {"message": "Producto desactivado"}

async def activate_product(role: str, user_id:str, email: str, product_id:str, request:Request):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    product_db = await products_repository.find_product_by_id(product_id=product_id)
    if not product_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    now=datetime.now(timezone.utc)
    result = await products_repository.activate_product(
        product_id=product_id,
        now=now
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado al modificar el stock"
        )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se aplicó ningún cambio"
        )
    await users_repository.add_user_history(
        email=email,
        action=AdminActions.ACTIVATE_PRODUCT,
        message=f"Activó el producto {product_db['name']}",
        request=request,
        role=role,
        entity="product",
        entity_id=str(product_id),
        now=now
    )
    return {"message": "Producto activado"}

async def products_dashboard(
    request: Request,
    blocked: bool = False,
    active: bool = True,
    low_stock: bool = False,
    out_of_stock: bool = False,
    with_discount: bool = False,
    order: str = "popular",
    search: str = "",
    page: int = 0,
    page_size: int = 8
):
    if page_size <= 0:
        page_size = 8
    and_conditions = []
    if blocked is not None:
        and_conditions.append({"is_blocked": blocked})
    if active is not None:
        and_conditions.append({"is_active": active})
    if with_discount:
        and_conditions.append({"discount": {"$gt": 0}})
    if low_stock:
        and_conditions.append({
            "computed_stock": {"$gt": 0, "$lte": 10}
        })
    if out_of_stock:
        and_conditions.append({
            "computed_stock": 0
        })
    if search:
        and_conditions.append({
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        })
    match = {"$and": and_conditions} if and_conditions else {}
    sort_map = {
        "price_asc": {"computed_price": 1},
        "price_desc": {"computed_price": -1},
        "stock_asc": {"computed_stock": 1},
        "stock_desc": {"computed_stock": -1},
        "newest": {"createdAt": -1},
        "oldest": {"createdAt": 1},
        "popular": {"popularity": -1}
    }
    sort = sort_map.get(order, {"createdAt": -1})
    cursor = products_repository.get_products_dashboard(
        match=match,
        sort=sort,
        page=page,
        page_size=page_size,
        add_popularity=True
    )
    result = await cursor.to_list(length=1)
    result = result[0] if result else {"data": [], "totalCount": []}
    products = result.get("data", [])
    total_count_list = result.get("totalCount", [])
    total_count = total_count_list[0]["count"] if total_count_list else 0
    products = [
        convert_dates(serialize_mongo(p), request.state.tz)
        for p in products
    ]
    for p in products:
        if "variants" in p:
            p["stock"] = sum(v["stock"] for v in p["variants"])
            p["price"] = min(v["price"] for v in p["variants"]) if p["variants"] else 0
        if "popularity" not in p:
            p["popularity"] = 0
        p["id"] = str(p.pop("_id"))
        await apply_discount_logic(p, PERU_TZ)
    effective_page_size = page_size - 1 if page == 0 else page_size
    return {
        "page": page,
        "page_size": effective_page_size,
        "total": total_count,
        "total_pages": math.ceil(total_count / page_size),
        "products": products
    }

async def get_all_catalogs():
    result = await products_repository.get_all_catalogs()
    return {"catalogs": result}