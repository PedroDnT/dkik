"""
Worker package initialization.

This module initializes the background worker package for the DKIK WhatsApp Bot,
which handles periodic tasks such as checking for case updates, sending notifications,
and managing scheduled reminders for court hearings.

The worker runs as a separate process from the main FastAPI application
and is responsible for all background and scheduled tasks.
"""

# Export worker components
from worker.scheduler import start_scheduler, stop_scheduler
from worker.tasks import (
    check_process_updates,
    send_hearing_reminders,
    clean_expired_subscriptions,
    process_notification_queue
)

__all__ = [
    "start_scheduler",
    "stop_scheduler",
    "check_process_updates",
    "send_hearing_reminders",
    "clean_expired_subscriptions",
    "process_notification_queue"
]
