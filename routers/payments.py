# routers/payments.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import stripe
import os
from database import get_db
from routers.auth import get_current_user_dependency

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
def create_checkout_session(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": 100,  # $1.00 per usage, adjust as needed
                        "product_data": {
                            "name": "Transcription Credit",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url="https://sheas-app.netlify.app/payment-success",
            cancel_url="https://sheas-app.netlify.app/payment-cancelled",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))