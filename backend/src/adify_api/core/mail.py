import asyncio
import smtplib
from email.message import EmailMessage

from adify_api.core.config import get_settings


class DeliveryError(Exception):
    pass


def _send(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"] = get_settings().mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    try:
        # smtplib blocks, so it runs off the event loop.
        await asyncio.to_thread(_send, message)
    except (OSError, smtplib.SMTPException) as error:
        raise DeliveryError(str(error)) from error
