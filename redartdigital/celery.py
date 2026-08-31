import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redartdigital.settings.local")

app = Celery("redartdigital")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Ensure project tasks are imported (project package is not a Django app).
app.conf.imports = ("redartdigital.tasks", "apps.edi.tasks")

# Fallback schedule (also registered into django-celery-beat DB on web startup).
app.conf.beat_schedule = {
    "cleanup-celery-storage-every-24h": {
        "task": "redartdigital.tasks.cleanup_celery_storage",
        # Daily at 00:00 UTC
        "schedule": crontab(minute=0, hour=0),
    },
}
