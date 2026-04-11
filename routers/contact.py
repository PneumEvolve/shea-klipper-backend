# routers/contact.py
 
import os
import logging
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from utils.email import send_email
 
logger = logging.getLogger(__name__)
 
router = APIRouter()
 
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "sheaklipper@gmail.com")
 
 
class ContactFormIn(BaseModel):
    name: str
    email: EmailStr
    message: str
 
 
@router.post("/contact/zen-freeskates")
def submit_zen_freeskates_contact(payload: ContactFormIn):
    """
    Receives a contact form submission from the Zen Freeskates page
    and sends a notification email to the admin.
    """
    subject = f"Zen Freeskates Lesson Request — {payload.name}"
 
    body = f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 2rem; color: #2c2c2a;">
 
      <h2 style="font-size: 1.2rem; margin-bottom: 1.5rem;">
        New lesson request from <strong>{payload.name}</strong>
      </h2>
 
      <p style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.5rem;">
        <strong>Name:</strong> {payload.name}
      </p>
 
      <p style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.5rem;">
        <strong>Email:</strong> <a href="mailto:{payload.email}" style="color: #2563eb;">{payload.email}</a>
      </p>
 
      <p style="font-size: 0.95rem; line-height: 1.7; margin-bottom: 0.5rem;">
        <strong>Message:</strong>
      </p>
 
      <p style="font-size: 0.95rem; line-height: 1.7; background: #f5f0e8; border-radius: 8px; padding: 1rem; margin-bottom: 2rem;">
        {payload.message}
      </p>
 
      <p style="font-size: 0.8rem; color: #aaa;">
        Sent via the Zen Freeskates contact form on PneumEvolve.
      </p>
 
    </div>
    """
 
    try:
        send_email(
            to_email=ADMIN_EMAIL,
            subject=subject,
            body=body,
        )
        logger.info(f"[contact] Zen Freeskates request from {payload.email}")
    except Exception as e:
        logger.error(f"[contact] Failed to send contact email: {e}")
        raise
 
    return {"status": "ok"}