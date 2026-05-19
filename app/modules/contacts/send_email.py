from fastapi_mail import MessageSchema
from typing import List
from app.core.config import settings
from app.modules.contacts.templates.request import request_email_template
from app.modules.contacts.templates.response_request import response_email_template
from app.modules.contacts.templates.pin import pin_email_template
from app.modules.contacts.templates.complaint_status_request import complaint_status_email_template
from app.modules.contacts.templates.order_template import order_email_template, admin_order_email_template, order_cancelled_email_client_template, order_cancelled_email_staff_template, order_delivered_email_template
from app.modules.contacts.templates import reclamation_template
import resend
from typing import List, Optional

resend.api_key = settings.RESEND_API_KEY

DEFAULT_FROM = "Musitec <noreply@musitecaqp.com>"

async def send_email_resend(
    to: List[str],
    subject: str,
    html: str,
    reply_to: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
):
    payload = {
        "from": DEFAULT_FROM,
        "to": to,
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if bcc:
        payload["bcc"] = bcc
    return resend.Emails.send(payload)

async def send_contact_email(name, email, subject, message):
    html_content = request_email_template(
        name=name,
        email=email,
        subject=subject,
        message=message
    )
    await send_email_resend(
        to=[settings.EMAIL_USER],
        subject=f"[Contacto] {subject}",
        html=html_content,
        reply_to=[email]
    )

async def send_response_email(email):
    html_content = response_email_template()
    await send_email_resend(
        to=[email],
        subject="[Contacto] Respuesta",
        html=html_content,
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )

async def send_pin_email(name: str, email: str, pin: str):
    html_content = pin_email_template(name=name, pin=pin)
    await send_email_resend(
        to=[email],
        subject="Pin de verificación",
        html=html_content,
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )

async def send_complaint_status_email(email, name, complaint_id, old_status, new_status):
    html_content = complaint_status_email_template(
        name=name,
        complaint_id=complaint_id,
        old_status=old_status,
        new_status=new_status,
        support_email=settings.EMAIL_USER
    )
    await send_email_resend(
        to=[email],
        subject="Actualización del reclamo",
        html=html_content,
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )

async def send_order_client_email(user_email, user_name, order):
    html_content = order_email_template(
        user_name=user_name,
        order=order
    )
    await send_email_resend(
        to=[user_email],
        subject="Gracias por su compra",
        html=html_content,
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )

async def send_order_staff_email(staff_emails, user_name, user_email, user_phone, order):
    staff_emails = staff_emails or []
    html_content = admin_order_email_template(
        user_name=user_name,
        user_email=user_email,
        user_phone=user_phone,
        order=order
    )
    try:
        await send_email_resend(
            to=[settings.EMAIL_USER],
            subject="Información de una orden",
            html=html_content,
            bcc=staff_emails,
            reply_to=[settings.PERSONAL_EMAIL]
        )
    except Exception as e:
        print(f"Order emails failed: {e}")

async def cancel_order_client_email(user_email, user_name, order):
    html_content = order_cancelled_email_client_template(
        user_name=user_name,
        order=order
    )
    await send_email_resend(
        to=[user_email],
        subject="Orden cancelada",
        html=html_content,
        reply_to=[settings.EMAIL_USER]
    )


async def cancel_order_staff_email(staff_emails, user_name, order):
    staff_emails = staff_emails or []

    html_content = order_cancelled_email_staff_template(
        user_name=user_name,
        order=order
    )
    await send_email_resend(
        to=[settings.EMAIL_USER],
        subject="Orden cancelada",
        html=html_content,
        bcc=staff_emails,
        reply_to=[settings.PERSONAL_EMAIL]
    )

async def delivery_order_email(user_email, user_name, order):
    html_content = order_delivered_email_template(
        user_name=user_name,
        order=order
    )
    await send_email_resend(
        to=[user_email],
        subject="Orden entregada",
        html=html_content,
        reply_to=[settings.EMAIL_USER]
    )

async def send_reclamation_client_email(
    name, complaint_id, order_id, reason, email_user, products=None
):
    html_content = reclamation_template.complaint_created_email_template(
        name=name,
        complaint_id=complaint_id,
        order_id=order_id,
        reason=reason,
        support_email=settings.EMAIL_USER,
        products=products
    )
    await send_email_resend(
        to=[email_user],
        subject="Tu reclamo fue realizado correctamente",
        html=html_content,
        reply_to=[settings.EMAIL_USER]
    )

async def send_update_reclamation_email(
    name, complaint_id, email_user, old_status, new_status, message, products=None
):
    html_content = reclamation_template.complaint_update_email_template(
        name=name,
        complaint_id=complaint_id,
        old_status=old_status,
        new_status=new_status,
        message=message,
        support_email=settings.EMAIL_USER,
        products=products
    )
    await send_email_resend(
        to=[email_user],
        subject="Actualización de tu reclamo",
        html=html_content,
        reply_to=[settings.EMAIL_USER]
    )

async def send_resolved_email(email_user, name, complaint_id, message, products=None):
    html_content = reclamation_template.complaint_resolved_email_template(
        name=name,
        complaint_id=complaint_id,
        message=message,
        support_email=settings.EMAIL_USER,
        products=products
    )
    await send_email_resend(
        to=[email_user],
        subject="Tu reclamo fue resuelto",
        html=html_content,
        reply_to=[settings.EMAIL_USER]
    )

async def send_reclamation_staff_email(
    complaint_id,
    user_name,
    user_email,
    order_id,
    reason,
    products,
    staff_emails
):
    staff_emails = staff_emails or []
    html_content = reclamation_template.complaint_staff_notification_template(
        complaint_id=complaint_id,
        user_name=user_name,
        user_email=user_email,
        order_id=order_id,
        reason=reason,
        products=products,
    )
    await send_email_resend(
        to=[settings.EMAIL_USER],
        subject="Nuevo reclamo",
        html=html_content,
        bcc=staff_emails,
        reply_to=[settings.PERSONAL_EMAIL]
    )