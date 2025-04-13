# routers/payments.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import stripe
import os
from database import get_db
from routers.auth import get_current_user_dependency
from fastapi.responses import JSONResponse

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
def create_checkout_session(current_user: dict = Depends(get_current_user_dependency)):
    try:
        # Example product: $1 = 1000 tokens
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Transcription Credits (1,000 tokens)",
                    },
                    "unit_amount": 100,  # $1.00 in cents
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=os.getenv("FRONTEND_URL") + "/payment-success",
            cancel_url=os.getenv("FRONTEND_URL") + "/payment-cancel",
            metadata={"user_id": current_user["id"]},
        )

        return JSONResponse({"url": session.url})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating Stripe session: {str(e)}")