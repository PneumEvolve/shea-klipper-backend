from fastapi import APIRouter, Request, HTTPException, Depends
import stripe
import os
from dotenv import load_dotenv
from models import User, TranscriptionUsage
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from routers.auth import get_current_user_dependency


load_dotenv()

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")  # This comes from Stripe dashboard

@router.post("/payments/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        print("❌ Invalid payload:", e)
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print("❌ Signature error:", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ✅ Listen for successful payment event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email", "unknown")
        print("✅ Payment completed for:", customer_email)

        # 🔁 Optionally: Log to database that this user paid
        # user = db.query(User).filter(User.email == customer_email).first()
        # create_paid_token_or_credit(user)

    return {"status": "success"}

def handle_payment_success(user_id: int, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.has_active_payment = True
        user.api_balance_dollars += 5.00  # Or whatever price you charge
        db.commit()

@router.get("/usage-balance")
def get_usage_balance(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    total_spent = db.query(func.sum(TranscriptionUsage.cost)).filter(
        TranscriptionUsage.user_id == current_user["id"]
    ).scalar() or 0.0

    # For example, give $5 of free credits for now
    free_credits = 5.00
    remaining = round(free_credits - total_spent, 4)

    return {"remaining_balance": max(remaining, 0.0)}

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency),
):
    try:
        # Define pricing — 1 token = $0.01, so $5 gives 500 tokens
        token_amount = 500
        price_in_cents = 500  # $5.00

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"{token_amount} Transcription Tokens",
                    },
                    "unit_amount": price_in_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=os.getenv("FRONTEND_URL", "http://localhost:5173") + "?success=true",
            cancel_url=os.getenv("FRONTEND_URL", "http://localhost:5173") + "?canceled=true",
            metadata={
                "user_id": str(current_user["id"]),
                "tokens_purchased": str(token_amount)
            }
        )

        return {"checkout_url": checkout_session.url}
    except Exception as e:
        print("❌ Stripe error:", str(e))
        raise HTTPException(status_code=500, detail="Failed to create checkout session")