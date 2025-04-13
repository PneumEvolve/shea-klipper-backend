import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv
import os

load_dotenv()

def send_email(to_email: str, subject: str, body: str):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    sender = {
        "name": "Shea Klipper",
        "email": os.getenv("FROM_EMAIL")  # e.g., your Brevo-verified email
    }

    to = [{"email": to_email}]

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject=subject,
        html_content=body
    )

    try:
        response = api_instance.send_transac_email(send_smtp_email)
        print("📨 Email sent successfully:", response)
    except ApiException as e:
        print("❌ Error sending email:", e)