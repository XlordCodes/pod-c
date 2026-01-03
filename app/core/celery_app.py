# app/core/celery_app.py
import os
from celery import Celery
from celery.schedules import crontab

# 1. Initialize Celery
celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

# 2. Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

# 3. Auto-discover tasks
celery_app.conf.imports = [
    "app.tasks.email_tasks",
    "app.tasks.whatsapp_tasks",
    "app.tasks.ai_tasks",
    "app.tasks.scheduler",
    "app.tasks.retry_tasks", # <--- NEW: Import the retry worker
]

# 4. Beat Schedule (Periodic Tasks)
celery_app.conf.beat_schedule = {
    # Existing Scheduler (Runs every minute)
    "check-scheduled-jobs-every-minute": {
        "task": "check_scheduled_jobs",
        "schedule": 60.0,
    },
    # NEW: Retry Worker (Runs every 5 minutes)
    "retry-failed-messages-every-5-min": {
        "task": "retry_failed_bulk_messages",
        "schedule": 300.0, 
    },
}