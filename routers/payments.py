from fastapi import APIRouter, Request, HTTPException
import stripe
import os
from dotenv import load_dotenv

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