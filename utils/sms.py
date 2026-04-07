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
    # Read at call time — not module load time — so Render env vars are always fresh
    sid   = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_FROM_NUMBER")

    logger.info(f"[sms] credentials present: SID={bool(sid)} TOKEN={bool(token)} FROM={bool(from_num)}")

    if not all([sid, token, from_num]):
        logger.warning("[sms] Twilio credentials not configured — skipping")
        return False

    number = to_number.strip()
    if not number.startswith("+"):
        number = "+" + number

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        message = client.messages.create(body=body, from_=from_num, to=number)
        logger.info(f"[sms] sent to {number} — sid: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"[sms] failed to send to {number}: {e}")
        raise