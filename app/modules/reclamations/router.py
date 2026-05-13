from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Request
from fastapi.responses import StreamingResponse
from app.modules.auth.dependencies import is_staff, is_client, get_current_user
from app.modules.reclamations import schemas, services
from pydantic import EmailStr
from typing import Optional, List
import json

router = APIRouter(prefix="/api/reclamations", tags=["Reclamations"])

@router.get("/order/{code}/items")
async def get_items(code: str, user_email: EmailStr):
    return await services.get_order_items_service(code=code, user_email=user_email)

@router.post("/reclamation")
async def create_reclamation(data:schemas.CreateReclamation, request:Request):
    return await services.create_reclamation(
        name=data.name,
        lastname=data.lastname,
        user_email=data.user_email,
        document_type=data.document_type,
        reclamation_type=data.reclamation_type,
        address=data.address,
        phone=data.phone,
        claimed_amount=data.claimed_amount,
        customer_request=data.customer_request,
        document_number=data.document_number,
        code=data.code,
        products=data.products,
        reason=data.reason,
        request=request
    )

@router.patch("/reclamation/{reclamation_id}/status")
async def update_reclamation_services(
    request:Request,
    reclamation_id: str,
    data: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    user=Depends(is_staff)
):
    parsed = schemas.UpdateReclamation(**json.loads(data))
    return await services.update_reclamation_service(
        employee_email=user["email"],
        reclamation_id=reclamation_id,
        myStatus=parsed.status,
        message=parsed.message,
        files=files,
        request=request
    )

@router.get("/reclamation/{reclamation_id}")
async def get_reclamation(request:Request,reclamation_id:str, user=Depends(get_current_user)):
    reclamation = await services.get_reclamation(request=request,id=reclamation_id)
    if not reclamation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reclamo no encontrado")
    user_is_staff = (user.get("role") == "admin" or user.get("role") == "moderator")
    user_is_owner = reclamation["user"]["email"] == user["email"]
    if not (user_is_staff or user_is_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    return reclamation

@router.patch("/reclamation/{reclamation_id}/reopen")
async def open_reclamation(reclamation_id:str, user=Depends(is_staff)):
    return await services.open_reclamation(
        reclamation_id=reclamation_id,
        staff_email=user["email"]
    )

@router.patch("/reclamation/{reclamation_id}/accept")
async def accept_reclamation(reclamation_id: str, user=Depends(is_client)):
    return await services.accept_reclamation(reclamation_id=reclamation_id, user=user)

@router.get("/reclamations/user")
async def get_user_reclamations(request:Request,page: int = 0, current_user=Depends(is_client)):
    return await services.get_user_reclamations(
        user_email=current_user["email"],
        page=page,
        request=request
    )

@router.get("/reclamations/staff")
async def get_reclamations(
    request:Request,
    user_email: Optional[EmailStr] = None,
    employee_email: Optional[EmailStr] = None,
    status: Optional[str] = None,
    is_closed: Optional[bool] = None,
    code: Optional[str] = None,
    page: int = 0,
    user=Depends(is_staff)
):
    return await services.get_reclamations(
        request=request,
        user_email=user_email,
        employee_email=employee_email,
        status=status,
        is_closed=is_closed,
        page=page,
        code=code
    )

@router.get("/reclamation/{id}/pdf")
async def download_pdf(request:Request,id:str, user=Depends(get_current_user)):
    reclamation = await services.get_reclamation(id=id, request=request)
    if not reclamation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reclamo no encontrado")
    user_is_staff = (user.get("role") == "admin" or user.get("role") == "moderator")
    user_is_owner = reclamation["user"]["email"] == user["email"]
    if not (user_is_staff or user_is_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
    pdf_buffer = await services.generate_reclamation_pdf(reclamation=reclamation)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=reclamo_{reclamation['code']}.pdf"
        }
    )