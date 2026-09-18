"""
schedule_notifications.py - CLI entry point for cron-based notification
generation (e.g. a Render Cron Job).

Runs one idempotent pass of the notification engine for every active
user at whatever slot is currently due in each user's timezone. Safe to
run multiple times - dedupe keys prevent any duplicate notifications.

Render Cron Job setup (for deployments where the web service is not
guaranteed to stay running):

    Command:  python schedule_notifications.py
    Schedule: 30 2 * * *   (02:30 UTC -> 08:00 Asia/Kolkata)
              30 6 * * *   (06:30 UTC -> 12:00 Asia/Kolkata)
              30 11 * * *  (11:30 UTC -> 17:00 Asia/Kolkata)

Requires the same environment variables as the web service
(DATABASE_URL / SECRET_KEY etc.).
"""
from app import app
from services.notifications.engine import (
    generate_due_notifications_for_all_users,
)

if __name__ == '__main__':
    with app.app_context():
        created = generate_due_notifications_for_all_users()
    print("Notifications generated: %d" % created)
