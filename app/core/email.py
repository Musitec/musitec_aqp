from fastapi_mail import FastMail, ConnectionConfig
from app.core.config import settings
conf = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_USER,
    MAIL_PASSWORD=settings.EMAIL_PASS,
    MAIL_FROM=settings.DEFAULT_FROM_EMAIL,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME="Musitec",
    TEMPLATE_FOLDER="app/modules/contacts/templates",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)
fastmail = FastMail(conf)