from app.modules.reclamations import repository as reclamations_repository
from app.modules.auth import repository as auth_repository
from app.modules.orders import repository as orders_repository
from app.modules.products import repository as products_repository
from app.modules.users_control import repository as users_repository
from app.modules.contacts import send_email
from typing import Optional,List,Dict
from app.modules.reclamations.schemas import ReclamationProduct
from pydantic import EmailStr
from datetime import datetime, timezone
from fastapi import HTTPException, status, Request
from app.cloudinary import upload_to_cloudinary
from app.core.convert_date import convert_dates
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from PIL import Image as PILImage
from app.core.config import settings
from io import BytesIO
import logging, re, requests

logger = logging.getLogger(__name__)

MAX_SIZE_MB = 5

MAX_FILES = 5

VALID_RECLAMATION_TYPES = {
    "reclamo",
    "queja"
}

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

VALID_DOCUMENT_TYPES = {
    "dni",
    "ce",
    "pasaporte",
    "ruc",
    "brevete"
}

LOGO_URL = "https://res.cloudinary.com/dm6vq2px2/image/upload/v1766340950/logo_hr4wk0.jpg"

class USER_ACTIONS:
    CREATE_RECLAMATION = "CREATE_RECLAMATION"
    UPDATE_RECLAMATION = "UPDATE_RECLAMATION"
    REOPEN_RECLAMATION = "REOPEN_RECLAMATION"
    ACCEPT_RECLAMATION = "ACCEPT_RECLAMATION"

def status_traductor(my_status):
    if my_status =="open":
        return "Abierto"
    elif my_status=="in_review":
        return "En revisión"
    elif my_status=="resolved":
        return "Resuelto"
    else:
        return "Rechazado"

async def process_evidences(files: List, now: datetime) -> List[dict]:
    if not files:
        return []

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo 5 imágenes permitidas"
        )
    validated_files = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es una imagen válida"
            )
        ext = file.filename.split(".")[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato no permitido: {ext}"
            )
        if file.size and file.size > MAX_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen supera el tamaño máximo permitido (5MB)"
            )
        try:
            img = PILImage.open(file.file)
            img.verify()
            file.file.seek(0)
            img = PILImage.open(file.file)
            if img.width > 5000 or img.height > 5000:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resolución de imagen demasiado grande"
                )
            file.file.seek(0)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archivo de imagen inválido o corrupto"
            )
        validated_files.append(file)
    results = await upload_to_cloudinary(validated_files, f"reclamations/{now.year}/{now.month}")
    uploaded = []
    timestamp = int(now.timestamp())
    for i, result in enumerate(results):
        uploaded.append({
            "url": result["url"],
            "public_id": result["public_id"],
            "uploaded_at": now,
            "type": "image",
            "order": i,
            "name": f"evidence_{timestamp}_{i}"
        })
    return uploaded

def get_logo_from_url(url: str):
    response = requests.get(url)
    if response.status_code != 200:
        return None
    img_bytes = BytesIO(response.content)
    return Image(img_bytes, width=4*cm, height=2*cm)

def normalize_option(value):
    return normalize_text(value or "") or None

def validate_dni(number: str) -> bool:
    if not number or len(number) != 8:
        return False
    if not number.isdigit():
        return False
    if number[0] == '0':
        return False
    return True

def validate_ce(number: str) -> bool:
    if not number or len(number) > 12:
        return False
    return bool(re.match(r'^[A-Z0-9]{1,12}$', number, re.IGNORECASE))

def validate_pasaporte(number: str) -> bool:
    if not number or len(number) < 6 or len(number) > 12:
        return False
    has_letter = bool(re.search(r'[A-Za-z]', number))
    has_number = bool(re.search(r'\d', number))
    return has_letter and has_number

def validate_ruc(number: str) -> bool:
    """Valida RUC: 11 dígitos"""
    if not number or len(number) != 11:
        return False
    if not number.isdigit():
        return False
    return True

def validate_brevete(number: str) -> bool:
    if not number or len(number) < 6 or len(number) > 12:
        return False
    return bool(re.match(r'^[A-Z0-9]{6,12}$', number))

def validate_document_number(document_type: str, document_number: str) -> bool:
    document_type = document_type.lower()
    if document_type == "dni":
        return validate_dni(document_number)
    elif document_type == "ce":
        return validate_ce(document_number)
    elif document_type == "pasaporte":
        return validate_pasaporte(document_number)
    elif document_type == "ruc":
        return validate_ruc(document_number)
    elif document_type == "brevete":
        return validate_brevete(document_number)
    else:
        return False

def normalize_text(text: str) -> str:
    if not text:
        return ""
    import unicodedata
    text = text.lower().strip()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    text = ' '.join(text.split())
    return text

def validate_reclamation_type(reclamation_type: str) -> bool:
    return reclamation_type.lower() in VALID_RECLAMATION_TYPES

async def enrich_reclamation_products(products):
    if not products:
        return None
    if isinstance(products[0], dict) and "name" in products[0]:
        return products
    product_ids = [p["product_id"] for p in products]
    product_db_map = await products_repository.get_products_by_ids(product_ids)
    enriched = []
    for p in products:
        product_db = product_db_map.get(p["product_id"])
        enriched.append({
            "name": p.get("name") or (product_db["name"] if product_db else "Producto eliminado"),
            "selected_option": p.get("selected_option"),
            "unit_price": p.get("unit_price")
        })
    return enriched

async def validate_order_by_email(order: dict, email: str):
    order_email = None
    if order.get("guest_info"):
        order_email = order["guest_info"].get("email")
    elif order.get("user_id"):
        user = await auth_repository.get_user_by_id(order["user_id"])
        if user:
            order_email = user.get("email")
    return order_email == email.lower().strip()

async def get_order_items_service(code: str, user_email: EmailStr):
    order = await orders_repository.get_order_by_code(code)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    is_valid = await validate_order_by_email(order, user_email)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta orden"
        )
    items = order.get("items", [])
    if not items:
        return []
    product_ids = [item["product_id"] for item in items]
    product_db_map = await products_repository.get_products_by_ids(product_ids)
    result = []
    for item in items:
        product_db = product_db_map.get(item["product_id"])
        result.append({
            "product_id": item.get("product_id"),
            "name": product_db["name"] if product_db else "Producto eliminado",
            "selected_option": item.get("selected_option"),
            "quantity": item.get("quantity")
        })
    return result

async def create_reclamation(
    name: str,
    lastname: str,
    user_email: EmailStr,
    document_type: str,
    address: str,
    phone: str,
    claimed_amount: Optional[float],
    customer_request: str,
    reclamation_type: str,
    document_number: str,
    code: str,
    products: Optional[List[ReclamationProduct]],
    reason: str,
    request: Request
):
    if not validate_reclamation_type(reclamation_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de reclamo inválido. Debe ser 'reclamo' o 'queja'. Recibido: {reclamation_type}"
        )
    if document_type.lower() not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de documento inválido. Tipos permitidos: {', '.join(VALID_DOCUMENT_TYPES)}"
        )
    if not validate_document_number(document_type, document_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El número de {document_type.upper()} no tiene un formato válido"
        )
    order = await orders_repository.get_order_by_code(code)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orden no encontrada"
        )
    if order.get("is_erased"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta orden fue eliminada"
        )
    selected_products = []
    order_items_map = {item["product_id"]: item for item in order.get("items", [])}
    seen = set()
    products = products or []
    product_ids = [p.product_id for p in products]
    product_db_map = await products_repository.get_products_by_ids(product_ids)
    for p in products:
        product_id = p.product_id
        option = normalize_option(p.selected_option or "")
        key = (product_id, option)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Productos duplicados en el reclamo"
            )
        seen.add(key)
        found_item = order_items_map.get(product_id)
        if not found_item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El producto con ID '{product_id}' no pertenece a la orden"
            )
        order_option = normalize_option(found_item.get("selected_option", ""))
        if order_option != option:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La opción seleccionada no coincide con la orden"
            )
        product_db = product_db_map.get(product_id)
        selected_products.append({
            "product_id": product_id,
            "name": product_db["name"] if product_db else "Producto eliminado",
            "selected_option": p.selected_option,
            "unit_price": product_db["price"] if product_db else None
        })
    now = datetime.now(timezone.utc)
    reclamation_code= await reclamations_repository.generate_reclamation_code(now=now)
    complaint_id = await reclamations_repository.create_reclamation(
        name=name,
        address=address,
        phone=phone,
        claimed_amount=claimed_amount,
        customer_request=customer_request,
        reclamation_code=reclamation_code,
        lastname=lastname,
        user_email=user_email,
        document_number=document_number,
        document_type=document_type,
        reclamation_type=reclamation_type,
        order_id=code,
        products=selected_products,
        reason=reason,
        now=now
    )
    if not complaint_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear el reclamo"
        )
    user = await auth_repository.get_user_by_email(email= user_email)
    if user:
        await users_repository.add_user_history(
            email=user_email,
            action=USER_ACTIONS.CREATE_RECLAMATION,
            message="Creó un reclamo",
            request=request,
            role=user.get("role", "user"),
            entity="reclamation",
            entity_id=reclamation_code,
            extra={
                "order_code": code,
                "type": reclamation_type
            },
            now=now
        )
    enriched_products = await enrich_reclamation_products(selected_products)
    try:
        staff_emails = await auth_repository.get_staff_emails(settings.EMAIL_USER)
        await send_email.send_reclamation_client_email(
            name=name + " " + lastname,
            complaint_id=reclamation_code,
            order_id= code,
            reason= reason,
            email_user=user_email,
            products=enriched_products
        )
        await send_email.send_reclamation_staff_email(
            complaint_id= reclamation_code,
            user_name=name + " " + lastname,
            user_email=user_email,
            order_id=code,
            reason=reason,
            products=enriched_products,
            staff_emails=staff_emails
        )
    except Exception as e:
        logger.error(f"Order emails failed: {e}")
    created_reclamation = await reclamations_repository.get_reclamation(complaint_id)
    return {
        "message": "Reclamo creado correctamente",
        "data": convert_dates(created_reclamation, request.state.tz)
    }

async def update_reclamation_service(
    employee_email: EmailStr,
    reclamation_id: str,
    myStatus: str,
    message: str,
    files: Optional[List] = None,
    request: Request = None 
):
    reclamation = await reclamations_repository.get_reclamation(reclamation_id)
    if not reclamation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reclamo no encontrado"
        )
    ALLOWED_TRANSITIONS = {
        "open": {"in_review", "rejected"},
        "in_review": {"resolved", "rejected"},
        "resolved": set(),
        "rejected": set()
    }
    current_status = reclamation.get("current_status")
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if myStatus not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transición de estado no válida"
        )
    if not message or not message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mensaje es obligatorio"
        )
    employee = await auth_repository.get_user_by_email(employee_email)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empleado no encontrado"
        )
    now = datetime.now(timezone.utc)
    evidences = None
    if files:
       if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Máximo 5 imágenes permitidas"
            )
       evidences = await process_evidences(files, now)
       logger.info(f"{employee_email} subió {len(files)} evidencias a {reclamation_id}")
    updated = await reclamations_repository.update_reclamation(
        employee_email=employee_email,
        reclamation_id=reclamation_id,
        is_closed = myStatus in {"resolved", "rejected"},
        current_status=current_status,
        status=myStatus,
        message=message,
        evidences=evidences,
        now=now
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el reclamo"
        )
    await users_repository.add_user_history(
        email=employee_email,
        action=USER_ACTIONS.UPDATE_RECLAMATION,
        message=f"Cambió estado de {status_traductor(current_status)} → {status_traductor(myStatus)}",
        request=request,
        role=employee.get("role", "staff"),
        entity="reclamation",
        entity_id=reclamation["code"],
        extra={
            "old_status": current_status,
            "new_status": myStatus
        },
        now=now
    )
    try:
        if myStatus == "resolved":
            await send_email.send_resolved_email(
                name=reclamation["user"]["name"],
                complaint_id=reclamation["code"],
                message="Tu reclamo fue resuelto satisfactoriamente.",
                email_user=reclamation["user"]["email"],
                products=reclamation.get("products")
            )
        elif myStatus == "rejected":
            await send_email.send_update_reclamation_email(
                name=reclamation["user"]["name"],
                complaint_id=reclamation["code"],
                old_status=reclamation["current_status"],
                new_status=myStatus,
                message="Tu reclamo fue evaluado y no procede.",
                email_user=reclamation["user"]["email"],
                products=reclamation.get("products")
            )
        else:
            await send_email.send_update_reclamation_email(
                name=reclamation["user"]["name"],
                complaint_id=reclamation["code"],
                old_status=current_status,
                new_status=myStatus,
                message=message,
                email_user=reclamation["user"]["email"],
                products=reclamation.get("products")
            )
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
    return {"message": "Reclamo actualizado correctamente"}

async def get_reclamation(
    id: str,
    request: Request,
):
    reclamation = await reclamations_repository.get_reclamation(
        reclamation_id=id
    )
    if not reclamation:
        return None
    reclamation["products"] = await enrich_reclamation_products(
        reclamation.get("products")
    )
    if "history" in reclamation and isinstance(reclamation["history"], list):
        reclamation["history"].sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
    return convert_dates(reclamation, request.state.tz)

async def open_reclamation(
    reclamation_id: str,
    staff_email: str
):
    reclamation = await reclamations_repository.get_reclamation(reclamation_id)
    if not reclamation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reclamo no encontrado"
        )
    if reclamation["current_status"] not in {"resolved", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden reabrir reclamos cerrados"
        )
    current_status = reclamation.get("current_status")
    now = datetime.now(timezone.utc)
    updated = await reclamations_repository.set_reclamation_status(
        employee_email=staff_email,
        reclamation_id=reclamation_id,
        current_status=current_status,
        is_closed=False,
        status="open",
        now=now
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el reclamo"
        )
    await users_repository.add_user_history(
        user_email=staff_email,
        action="REOPEN_RECLAMATION",
        entity_id=reclamation["code"],
        description="Reabrió un reclamo",
        metadata={
            "old_status": current_status,
            "new_status": "open"
        },
        now=now
    )
    return {
        "message": "Reclamo reabierto correctamente"
    }

async def get_user_reclamations(request:Request,user_email: EmailStr, page: int = 0):
    try:
        cursor = await reclamations_repository.get_user_reclamations(user_email=user_email,page=page)
        results = []
        data = cursor.get("data", [])
        for doc in data:
            doc["products"] = await enrich_reclamation_products(
                doc.get("products")
            )
            results.append(convert_dates(doc, request.state.tz))    
        return {
            "data": results,
            "total": cursor.get("total"),
            "page": page,
            "pages": cursor.get("pages")
        }
    except Exception as e:
        print(f"Error: {e}")
        return None
    
async def get_reclamations(
    request: Request,
    user_email: Optional[EmailStr] = None,
    employee_email: Optional[EmailStr] = None,
    status: Optional[str] = None,
    is_closed: Optional[bool] = None,
    code: Optional[str] = None,
    page: int = 0
):
    try:
        cursor = await reclamations_repository.get_reclamations(
            page=page,
            user_email=user_email,
            employee_email=employee_email,
            status=status,
            is_closed=is_closed,
            code=code
        )
        results = []
        data = cursor.get("data", [])
        for doc in data:
            doc["products"] = await enrich_reclamation_products(
                doc.get("products")
            )
            results.append(convert_dates(doc, request.state.tz))   
        return {
            "data": results,
            "total": cursor.get("total"),
            "page": page,
            "pages": cursor.get("pages")
        }
    except Exception as e:
        print(f"Error: {e}")
        return None
    
async def accept_reclamation(reclamation_id: str, user:dict):
    reclamation = await reclamations_repository.get_reclamation(reclamation_id)
    if not reclamation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reclamo no encontrado"
        )
    print(f"Correo del reclamo: {reclamation['user']['email']}")
    user_email = reclamation.get("user", {}).get("email")
    if user_email != user.get("email"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado"
        )
    now = datetime.now(timezone.utc)
    result = await reclamations_repository.accept_reclamation(
        reclamation_id=reclamation_id,
        now=now
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error al actualizar el reclamo")
    await users_repository.add_user_history(
        user_email=user["email"],
        action=USER_ACTIONS.ACCEPT_RECLAMATION,
        entity_id=reclamation["code"],
        description="Aceptó el resultado (aceptado)",
        metadata={
            "old_status": reclamation.get("current_status"),
            "new_status": "resolved"
        },
        now=now
    )
    return {
        "message":"Resultado aceptado correctamente"
    }

def format_date(dt):
    if not dt:
        return "-"
    return dt.strftime("%d/%m/%Y %H:%M")

async def generate_reclamation_pdf(reclamation: dict):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()
    elements = []
    logo = get_logo_from_url(LOGO_URL)
    if logo:
        elements.append(logo)
        elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>LIBRO DE RECLAMACIONES</b>", styles["Title"]))
    elements.append(Spacer(1, 10))
    company = reclamation.get("company", {})
    elements.append(Paragraph("<b>7. CANALES DE ATENCIÓN</b>", styles["Heading3"]))
    elements.append(Paragraph(
        f"Canal de respuesta: {reclamation.get('response_channel', '-')}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Canal de soporte: {reclamation.get('support_channel', '-')}",
        styles["Normal"]
    ))
    elements.append(Paragraph("<b>1. IDENTIFICACIÓN DEL PROVEEDOR</b>", styles["Heading3"]))
    elements.append(Paragraph(f"Empresa: {company.get('name', '')}", styles["Normal"]))
    elements.append(Paragraph(f"RUC: {company.get('ruc', '')}", styles["Normal"]))
    elements.append(Paragraph(f"Dirección: {company.get('address', '')}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>2. IDENTIFICACIÓN DEL RECLAMO</b>", styles["Heading3"]))
    elements.append(Paragraph(f"Código: {reclamation.get('code')}", styles["Normal"]))
    elements.append(Paragraph(f"Fecha: {format_date(reclamation.get('created_at'))}", styles["Normal"]))
    elements.append(Paragraph(f"Tipo: {reclamation.get('type').capitalize()}", styles["Normal"]))
    elements.append(Paragraph(f"Monto reclamado: S/ {reclamation.get('claimed_amount') or '0.00'}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    user = reclamation.get("user", {})
    elements.append(Paragraph("<b>3. DATOS DEL CONSUMIDOR</b>", styles["Heading3"]))
    elements.append(Paragraph(f"{user.get('name')} {user.get('lastname')}", styles["Normal"]))
    elements.append(Paragraph(f"{user.get('document_type').upper()}: {user.get('document_number')}", styles["Normal"]))
    elements.append(Paragraph(f"Email: {user.get('email')}", styles["Normal"]))
    elements.append(Paragraph(f"Teléfono: {user.get('phone')}", styles["Normal"]))
    elements.append(Paragraph(f"Dirección: {user.get('address')}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>4. DETALLE DEL RECLAMO</b>", styles["Heading3"]))
    elements.append(Paragraph(f"Motivo: {reclamation.get('reason')}", styles["Normal"]))
    elements.append(Paragraph(f"Pedido del cliente: {reclamation.get('customer_request')}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    history = reclamation.get("history", [])
    if history:
        history = sorted(history, key=lambda x: x.get("date", ""))
        elements.append(Paragraph("<b>8. HISTORIAL DEL RECLAMO</b>", styles["Heading3"]))
        elements.append(Spacer(1, 10))
        for h in history:
            elements.append(Paragraph(
                f"<b>Fecha:</b> {format_date(h.get('date'))}",
                styles["Normal"]
            ))
            elements.append(Paragraph(
                f"<b>Mensaje:</b> {h.get('message')}",
                styles["Normal"]
            ))
            elements.append(Paragraph(
                f"<b>Cambio de estado:</b> {status_traductor(h.get('old_status'))} → {status_traductor(h.get('new_status'))}",
                styles["Normal"]
            ))
            elements.append(Paragraph(
                f"<b>Responsable:</b> {h.get('changed_by')}",
                styles["Normal"]
            ))
            if h.get("evidences"):
                for ev in h["evidences"]:
                    elements.append(Paragraph(f"Evidencia: {ev['url']}", styles["Normal"]))
            elements.append(Spacer(1, 10))
    products = reclamation.get("products", [])
    if products:
        elements.append(Paragraph("<b>5. PRODUCTOS / SERVICIOS</b>", styles["Heading3"]))
        data = [["Producto", "Opción", "Precio"]]
        for p in products:
            data.append([
                p.get("name"),
                p.get("selected_option") or "-",
                f"S/ {p.get('unit_price') or '-'}"
            ])
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>6. ESTADO DEL RECLAMO</b>", styles["Heading3"]))
    elements.append(Paragraph(f"Estado actual: {status_traductor(reclamation.get('current_status'))}", styles["Normal"]))
    elements.append(Paragraph(f"Fecha límite: {format_date(reclamation.get('due_date'))}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>7. ACEPTACIÓN DEL CONSUMIDOR</b>", styles["Heading3"]))
    elements.append(Paragraph(
        f"Aceptó términos: {'Sí' if reclamation.get('accepted_terms') else 'No'}",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        f"Fecha de aceptación: {format_date(reclamation.get('accepted_at'))}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Este documento constituye una constancia del registro en el Libro de Reclamaciones conforme a la normativa de INDECOPI.",
        styles["Italic"]
    ))
    doc.build(elements)
    buffer.seek(0)
    return buffer