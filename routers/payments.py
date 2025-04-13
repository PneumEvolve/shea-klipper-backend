from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models import TranscriptionUsage
from database import get_db
import os
import stripe

router = APIRouter()

# Load Stripe secret key from environment
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/payments/create-checkout-session")
def create_checkout_session(transcription_id: int, db: Session = Depends(get_db)):
    # Step 1: Look up transcription usage from DB
    usage = db.query(TranscriptionUsage).filter(
        TranscriptionUsage.transcription_id == transcription_id
    ).first()

    if not usage:
        raise HTTPException(status_code=404, detail="Transcription usage not found")

    # Step 2: Calculate Stripe-compatible cost in cents
    cost_per_1000_tokens = 0.01  # USD per 1000 tokens
    amount = int((usage.tokens_used / 1000) * cost_per_1000_tokens * 100)

    if amount < 1:
        amount = 1  # Minimum of $0.01 to avoid Stripe errors

    # Step 3: Create a Stripe Checkout session
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Transcription ID: {transcription_id}",
                    },
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://sheas-app.netlify.app/payment-success",
            cancel_url="https://sheas-app.netlify.app/payment-cancel",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))