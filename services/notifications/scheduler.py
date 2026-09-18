"""
services/notifications/scheduler.py

Server-side notification scheduling. Runs the engine's
generate_due_notifications_for_all_users() for every active user at the
configured slot hours (08:00 / 12:00 / 17:00 in each user's timezone).

Two deployment modes are supported (both idempotent - dedupe keys in the
engine make concurrent/repeated runs harmless):

1. In-process background thread (start_notification_scheduler): used
   automatically by `python app.py`. Covers always-on deployments such
   as a Render Web Service that never stops.

2. Cron entry point (schedule_notifications.py at the repo root): for
   platforms that spin workers down (e.g. Render free tier) attach a
   Render Cron Job running that script at 02:30/06:30/11:30 UTC, which
   covers the 08:00/12:00/17:00 Asia/Kolkata slots.

The thread checks every NOTIFY_SCHEDULER_INTERVAL_MINUTES (default 10)
and generates for any user whose slot is due; a user who was offline
when their slot passed still gets the slot's notifications on the first
check after their slot (the engine computes the "latest slot that has
already passed today" per user timezone).
"""
import os
import threading
import time

from utils.logger import get_logger

logger = get_logger()

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _interval_seconds() -> int:
    try:
        return max(60, int(os.environ.get(
            'NOTIFY_SCHEDULER_INTERVAL_MINUTES', '10')) * 60)
    except (TypeError, ValueError):
        return 600


def _run_once(app) -> None:
    """One scheduler pass inside an app context; never raises."""
    try:
        with app.app_context():
            from services.notifications.engine import (
                generate_due_notifications_for_all_users,
            )
            created = generate_due_notifications_for_all_users()
            if created:
                logger.info("Notification scheduler generated %d notifications",
                            created)
    except Exception as exc:  # pragma: no cover - the thread must not die
        logger.warning("Notification scheduler pass failed: %s", exc)


def _loop(app, interval: int) -> None:
    # First run after the interval, not at boot - avoids heavy work while
    # the app is still starting up and keeps short-lived test runs silent.
    time.sleep(interval)
    while True:
        _run_once(app)
        time.sleep(interval)


def start_notification_scheduler(app) -> threading.Thread:
    """Start the background scheduler thread once per process."""
    global _scheduler_started
    if os.environ.get('NOTIFY_SCHEDULER_ENABLED', '1').strip().lower() \
            in ('0', 'false', 'no'):
        logger.info("Notification scheduler disabled by env")
        return None
    with _scheduler_lock:
        if _scheduler_started:
            return None
        _scheduler_started = True
    thread = threading.Thread(
        target=_loop, args=(app, _interval_seconds()),
        name='notification-scheduler', daemon=True)
    thread.start()
    logger.info("Notification scheduler started (interval %ds)",
                _interval_seconds())
    return thread
