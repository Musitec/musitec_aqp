from fastapi_mail import MessageSchema
from typing import List
from app.core.email import fastmail
from app.core.config import settings
from app.modules.contacts.templates.request import request_email_template
from app.modules.contacts.templates.response_request import response_email_template
from app.modules.contacts.templates.pin import pin_email_template
from app.modules.contacts.templates.complaint_status_request import complaint_status_email_template
from app.modules.contacts.templates.order_template import order_email_template, admin_order_email_template, order_cancelled_email_client_template, order_cancelled_email_staff_template, order_delivered_email_template
from app.modules.contacts.templates import reclamation_template

async def send_contact_email(name, email, subject, message):
    html_content = request_email_template(
        name=name,
        email=email,
        subject=subject,
        message=message
    )
    message = MessageSchema(
        subject=f"[Contacto] {subject}",
        recipients=[settings.EMAIL_USER],
        body=html_content,
        subtype="html",
        reply_to=[email]
    )
    await fastmail.send_message(message)

async def send_response_email(email):
    html_content = response_email_template()
    message = MessageSchema(
        subject="[Contacto] Respuesta",
        recipients=[email],
        body=html_content,
        subtype="html",
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )
    await fastmail.send_message(message)

async def send_pin_email(name: str, email: str, pin: str):
    html_content = pin_email_template(name=name, pin=pin)
    message = MessageSchema(
        subject="Pin de verificación",
        recipients=[email],
        body=html_content,
        subtype="html",
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )
    await fastmail.send_message(message)

async def send_complaint_status_email(email:str,name:str,complaint_id:str,old_status:str,new_status:str):
    html_content = complaint_status_email_template(
        name=name,
        complaint_id=complaint_id,
        old_status=old_status,
        new_status=new_status,
        support_email=settings.EMAIL_USER
    )
    message = MessageSchema(
        subject="Actualización del reclamo",
        recipients=[email],
        body=html_content,
        subtype="html",
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )
    await fastmail.send_message(message)

async def send_order_client_email(user_email:str, user_name: str, order: dict):
    html_content = order_email_template(
        user_name=user_name,
        order=order
    )
    message = MessageSchema(
        subject="Gracias por su compra",
        recipients=[user_email],
        body=html_content,
        subtype="html",
        reply_to=[settings.DEFAULT_FROM_EMAIL]
    )
    await fastmail.send_message(message)

async def send_order_staff_email(staff_emails: list[str] | None, user_name: str, user_email: str, user_phone: str, order: dict):
    staff_emails = staff_emails or []
    html_content = admin_order_email_template(
        user_name=user_name,
        user_email=user_email,
        user_phone=user_phone,
        order=order
    )
    message=MessageSchema(
        subject="Información de una orden",
        recipients=[settings.EMAIL_USER],
        bcc=staff_emails,
        body=html_content,
        subtype="html",
        reply_to=[settings.PERSONAL_EMAIL]
    )
    try:
        await fastmail.send_message(message)
    except Exception as e:
        print(f"Order emails failed: {e}")

async def cancel_order_client_email(user_email:str, user_name: str, order: dict):
    html_content = order_cancelled_email_client_template(
        user_name=user_name,
        order=order
    )
    message=MessageSchema(
        subject="Orden cancelada",
        recipients=[user_email],
        body=html_content,
        subtype="html",
        reply_to=[settings.EMAIL_USER]
    )
    await fastmail.send_message(message)

async def cancel_order_staff_email(staff_emails: list[str] | None, user_name: str, order: dict):
    staff_emails = staff_emails or []
    html_content = order_cancelled_email_staff_template(
        user_name=user_name,
        order=order
    )
    message=MessageSchema(
        subject="Orden cancelada",
        recipients=[settings.EMAIL_USER],
        bcc=staff_emails,
        body=html_content,
        subtype="html",
        reply_to=[settings.PERSONAL_EMAIL]
    )
    await fastmail.send_message(message)

async def delivery_order_email(user_email:str, user_name: str, order: dict):
    html_content = order_delivered_email_template(
        user_name=user_name,
        order=order
    )
    message=MessageSchema(
        subject="Orden entregada",
        recipients=[user_email],
        body=html_content,
        subtype="html",
        reply_to=[settings.EMAIL_USER]
    )
    await fastmail.send_message(message)

async def send_reclamation_client_email(
    name: str,
    complaint_id: str,
    order_id: str,
    reason: str,
    email_user: str,
    products: list | None = None
):
    html_content = reclamation_template.complaint_created_email_template(
        name=name,
        complaint_id=complaint_id,
        order_id=order_id,
        reason=reason,
        support_email=settings.EMAIL_USER,
        products=products
    )
    message= MessageSchema(
        subject="Tu reclamo fue realizado correctamente",
        recipients=[email_user],
        body= html_content,
        subtype="html",
        reply_to=[settings.EMAIL_USER]
    )
    await fastmail.send_message(message)

async def send_update_reclamation_email(
    name: str,
    complaint_id: str,
    email_user: str,
    old_status: str,
    new_status: str,
    message: str,
    products: list | None = None
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
    message= MessageSchema(
        subject="Tu reclamo fue realizado correctamente",
        recipients=[email_user],
        body= html_content,
        subtype="html",
        reply_to=[settings.EMAIL_USER]
    )
    await fastmail.send_message(message)

async def send_resolved_email(
    email_user: str,
    name: str,
    complaint_id: str,
    message: str,
    products: list | None = None
):
    html_content = reclamation_template.complaint_resolved_email_template(
        name=name,
        complaint_id=complaint_id,
        message=message,
        support_email=settings.EMAIL_USER,
        products=products
    )
    message= MessageSchema(
        subject="Tu reclamo fue realizado correctamente",
        recipients=[email_user],
        body= html_content,
        subtype="html",
        reply_to=[settings.EMAIL_USER]
    )
    await fastmail.send_message(message)

async def send_reclamation_staff_email(
    complaint_id: str,
    user_name: str,
    user_email: str,
    order_id: str,
    reason: str,
    products: list | None,
    staff_emails: list[str] | None
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
    message=MessageSchema(
        subject="Nuevo reclamo",
        recipients=[settings.EMAIL_USER],
        bcc=staff_emails,
        body=html_content,
        subtype="html",
        reply_to=[settings.PERSONAL_EMAIL]
    )
    await fastmail.send_message(message)