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
 
logger = logging.getLogger(__name__)
 
NOTIFY_SECONDS_BEFORE = 120  # 2 minutes before window
WINDOW_SECONDS = 300          # must match stillness.py
 
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://pneumevolve.com")
# Unsubscribe hits the API directly since the backend serves the confirmation HTML page
API_URL = os.getenv("API_URL", "https://api.pneumevolve.com")
 
 
def check_and_notify_stillness():
    """
    Called by APScheduler every minute.
    Sends one email per user per group per day, ~2 minutes before their window.
    Respects unsubscribe prefs and skips users who opted out.
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
 
            members = db.execute(
                text("""
                    SELECT u.id, u.email, u.username
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
 
                # Check unsubscribe pref — skip if opted out
                pref = db.execute(
                    text("""
                        SELECT email_enabled FROM stillness_notification_prefs
                        WHERE user_id = :u AND group_id = :g
                    """),
                    {"u": user_id, "g": group_id},
                ).first()
 
                if pref and not pref[0]:
                    logger.info(f"[stillness] skipping {email} for '{group_name}' (unsubscribed)")
                    continue
 
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
 
                # Generate unsubscribe token
                from routers.stillness import make_unsubscribe_token
                unsub_token = make_unsubscribe_token(user_id, group_id)
                unsub_url = f"{API_URL}/stillness/unsubscribe?token={unsub_token}"
 
                try:
                    send_email(
                        to_email=email,
                        subject=f"Your stillness moment is starting — {group_name}",
                        body=_build_email(username, group_name, seconds_until_open, unsub_url),
                    )
 
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
 
                    logger.info(
                        f"[stillness] emailed {email} for '{group_name}' "
                        f"(window opens in {int(seconds_until_open)}s)"
                    )
 
                except Exception as e:
                    logger.error(f"[stillness] failed to email {email}: {e}")
                    db.rollback()
 
    except Exception as e:
        logger.error(f"[stillness scheduler] unexpected error: {e}")
    finally:
        db.close()
 
 
def _build_email(username: str, group_name: str, seconds_until: float, unsub_url: str) -> str:
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
 
      <a href="https://pneumevolve.com/stillness"
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