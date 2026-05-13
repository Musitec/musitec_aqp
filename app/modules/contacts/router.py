from fastapi import APIRouter, HTTPException, status
from app.modules.contacts.schema import ContactRequest
from app.modules.contacts.send_email import send_contact_email,send_response_email

router = APIRouter(prefix="/api/contact", tags=["Contact"])

@router.post("/send-request", status_code=status.HTTP_200_OK)
async def send_contact(request: ContactRequest):
    try:
        await send_contact_email(
            name=request.name,
            email=request.email,
            subject=request.subject,
            message=request.message
        )
        await send_response_email(email=request.email)
        return {"message": "Correo enviado correctamente"}
    except Exception as e:
        print("Error",e)
        raise HTTPException(
            status_code=500,
            detail="Error al enviar el correo"
        )