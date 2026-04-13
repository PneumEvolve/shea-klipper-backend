# utils/stillness_scheduler.py
 
import logging
import os
from datetime import datetime, timezone, timedelta, time
from dotenv import load_dotenv
 
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))
 
from sqlalchemy import text
from database import SessionLocal
from utils.email import send_email
from utils.sms import send_sms
from routers.stillness import make_unsubscribe_token
 
logger = logging.getLogger(__name__)
 
NOTIFY_SECONDS_BEFORE = 60  # 2 minutes before window
WINDOW_SECONDS = 300          # must match stillness.py
 
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://pneumevolve.com")
API_URL = os.getenv("API_URL", "https://api.pneumevolve.com")
 
 
def check_and_notify_stillness():
    """
    Called by APScheduler every minute.
    Sends email and/or SMS to each member ~2 minutes before their window opens.
    Respects unsubscribe prefs. Never double-sends on the same day.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        today = now.date()
 
        groups = db.execute(
            text("SELECT id, name, daily_time_utc FROM stillness_groups WHERE daily_time_utc IS NOT NULL")
        ).mappings().all()
 
        for group in groups:
            raw_time = group["daily_time_utc"]
            daily_time = time.fromisoformat(raw_time) if isinstance(raw_time, str) else raw_time
 
            window_start = datetime(
                now.year, now.month, now.day,
                daily_time.hour, daily_time.minute, 0,
                tzinfo=timezone.utc,
            )
            window_end = window_start + timedelta(seconds=WINDOW_SECONDS)
            seconds_until_open = (window_start - now).total_seconds()
 
            if not (0 <= seconds_until_open <= NOTIFY_SECONDS_BEFORE):
                continue
            if now >= window_end:
                continue
 
            group_id = group["id"]
            group_name = group["name"]
 
            # Fetch members with email and phone
            members = db.execute(
                text("""
                    SELECT u.id, u.email, u.username, u.phone_number
                    FROM stillness_members m
                    JOIN users u ON u.id = m.user_id
                    WHERE m.group_id = :g
                """),
                {"g": group_id},
            ).mappings().all()
 
            for member in members:
                user_id = member["id"]
                email = member["email"]
                username = member["username"] or "there"
                phone = member["phone_number"]
                print(f"DEBUG member: {email}, phone: {phone}")
 
                # Check unsubscribe pref
                pref = db.execute(
                    text("""
                        SELECT email_enabled, sms_enabled FROM stillness_notification_prefs
                        WHERE user_id = :u AND group_id = :g
                    """),
                    {"u": user_id, "g": group_id},
                ).mappings().first()

                email_enabled = pref["email_enabled"] if pref else True
                sms_enabled = pref["sms_enabled"] if pref else True
 
                # Check if already notified today
                already_sent = db.execute(
                    text("""
                        SELECT id FROM stillness_notifications_sent
                        WHERE group_id = :g AND user_id = :u AND sent_for_date = :d
                    """),
                    {"g": group_id, "u": user_id, "d": today},
                ).first()
 
                if already_sent:
                    continue
 
                # Generate unsubscribe token for email
                
                unsub_token = make_unsubscribe_token(user_id, group_id)
                unsub_url = f"{API_URL}/stillness/unsubscribe?token={unsub_token}"
 
                email_sent = False
                sms_sent = False
 
               # Send email
                if email_enabled:
                    try:
                        send_email(
                            to_email=email,
                            subject=f"Your stillness moment is starting — {group_name}",
                            body=_build_email(username, group_name, seconds_until_open, unsub_url, group_id),
                     )
                        email_sent = True
                        logger.info(f"[stillness] emailed {email} for '{group_name}'")
                    except Exception as e:
                        logger.error(f"[stillness] email failed for {email}: {e}")

                # Send SMS
                if phone and sms_enabled:
                    try:
                        sms_sent = send_sms(
                            to_number=phone,
                            body=_build_sms(group_name, seconds_until_open, group_id),
                        )
                        if sms_sent:
                            logger.info(f"[stillness] SMS sent to {phone} for '{group_name}'")
                        else:
                            logger.warning(f"[stillness] SMS skipped for {phone}")
                    except Exception as e:
                        logger.error(f"[stillness] SMS failed for {phone}: {e}")
 
                # Record as notified if at least one channel succeeded
                if email_sent or sms_sent:
                    try:
                        db.execute(
                            text("""
                                INSERT INTO stillness_notifications_sent
                                    (group_id, user_id, sent_for_date)
                                VALUES (:g, :u, :d)
                                ON CONFLICT (group_id, user_id, sent_for_date) DO NOTHING
                            """),
                            {"g": group_id, "u": user_id, "d": today},
                        )
                        db.commit()
                    except Exception as e:
                        logger.error(f"[stillness] failed to record notification: {e}")
                        db.rollback()
 
    except Exception as e:
        logger.error(f"[stillness scheduler] unexpected error: {e}")
        raise
    finally:
        db.close()
 
 
def _build_sms(group_name: str, seconds_until: float, group_id: int) -> str:
    minutes = max(1, int(seconds_until // 60))
    when = "now" if minutes < 2 else f"in {minutes} min"
    return (
        f"Your stillness moment with {group_name} is starting {when}. "
        f"Open the app and tap the circle. {FRONTEND_URL}/stillness/{group_id}"
    )
 
 
def _build_email(username: str, group_name: str, seconds_until: float, unsub_url: str, group_id: int) -> str:
    minutes = max(1, int(seconds_until // 60))
    when = "right now" if minutes < 2 else f"in about {minutes} minutes"
 
    return f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 2rem; color: #2c2c2a;">
 
      <p style="font-size: 1.1rem; margin-bottom: 1.5rem;">
        Hi {username},
      </p>
 
      <p style="font-size: 1rem; line-height: 1.7; margin-bottom: 1.5rem;">
        Your shared stillness moment with <strong>{group_name}</strong>
        is opening <strong>{when}</strong>.
      </p>
 
      <p style="font-size: 0.95rem; line-height: 1.7; color: #555; margin-bottom: 2rem;">
        Open the app and tap the circle when you're ready.
        You have five minutes. No pressure if you miss it.
      </p>
 
      <a href="{FRONTEND_URL}/stillness/{group_id}"
         style="display: inline-block; padding: 0.75rem 1.5rem;
                background: #f5f0e8; border: 1px solid #d4c9b0;
                border-radius: 8px; text-decoration: none;
                color: #2c2c2a; font-size: 0.9rem;">
        Open Shared Stillness →
      </a>
 
      <p style="margin-top: 3rem; font-size: 0.72rem; color: #bbb; line-height: 1.6;">
        You're receiving this because you're part of a Shared Stillness group on PneumEvolve.<br>
        <a href="{unsub_url}" style="color: #bbb;">Unsubscribe from notifications for {group_name}</a>
      </p>
 
    </div>
    """