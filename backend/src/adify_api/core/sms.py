import logging

from adify_api.core.mail import send_email

logger = logging.getLogger(__name__)


async def send_sms(phone: str, text: str) -> None:
    """Development outbox until an SMS vendor is chosen (SW-003, vendor TBD).

    Messages are mailed to the configured SMTP server, which is Mailpit locally,
    so the code can be read there; no real SMS is sent.
    """
    logger.info("SMS to %s: %s", phone, text)
    await send_email(f"{phone.lstrip('+')}@sms-outbox.adify.local", f"SMS to {phone}", text)
