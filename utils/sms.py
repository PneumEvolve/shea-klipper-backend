# utils/sms.py
#
# Thin wrapper around Twilio for sending SMS.
# Install with: pip install twilio
 
import logging
import os
from dotenv import load_dotenv
 
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))
 
logger = logging.getLogger(__name__)
 
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
 
 
def send_sms(to_number: str, body: str) -> bool:
    """
    Send an SMS via Twilio.
    Returns True on success, False on failure.
    Raises on error so the caller can handle it.
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER]):
        logger.warning("[sms] Twilio credentials not configured — skipping SMS")
        return False
 
    # Normalize number — ensure it starts with +
    number = to_number.strip()
    if not number.startswith("+"):
        number = "+" + number
 
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=TWILIO_FROM_NUMBER,
            to=number,
        )
        logger.info(f"[sms] sent to {number} — sid: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"[sms] failed to send to {number}: {e}")
        raise