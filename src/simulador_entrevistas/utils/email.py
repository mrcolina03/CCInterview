from email.message import EmailMessage
from aiosmtplib import send
import os

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


async def enviar_correo(destinatario: str, asunto: str, contenido: str):
    mensaje = EmailMessage()
    mensaje["From"] = EMAIL_FROM
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(contenido, subtype="html")

    await send(
        mensaje,
        hostname="smtp.gmail.com",
        port=587,
        start_tls=True,
        username=EMAIL_FROM,
        password=EMAIL_PASSWORD
    )
