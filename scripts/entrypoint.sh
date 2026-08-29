#!/usr/bin/env bash
# ========
# Container entrypoint
# Roles: web | worker | beat | shell
# ========
set -euo pipefail

# ========
# Wait for Postgres
# ========
wait_for_postgres() {
  echo "[entrypoint] Waiting for Postgres at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432} ..."
  python - <<'PY'
import os
import time

import psycopg

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
user = os.environ.get("POSTGRES_USER", "edi")
password = os.environ.get("POSTGRES_PASSWORD", "edi")
dbname = os.environ.get("POSTGRES_DB", "edi")

deadline = time.time() + 60
while True:
    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            connect_timeout=3,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("[entrypoint] Postgres is ready.")
        break
    except Exception as exc:
        if time.time() > deadline:
            raise SystemExit(f"[entrypoint] Postgres not ready: {exc}") from exc
        time.sleep(2)
PY
}

# ========
# Wait for Redis
# ========
wait_for_redis() {
  echo "[entrypoint] Waiting for Redis ..."
  python - <<'PY'
import os
import time
from urllib.parse import urlparse

import redis

url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
parsed = urlparse(url)
host = parsed.hostname or "redis"
port = parsed.port or 6379

deadline = time.time() + 60
client = redis.Redis(host=host, port=port, socket_connect_timeout=3)
while True:
    try:
        client.ping()
        print("[entrypoint] Redis is ready.")
        break
    except Exception as exc:
        if time.time() > deadline:
            raise SystemExit(f"[entrypoint] Redis not ready: {exc}") from exc
        time.sleep(2)
PY
}

# ========
# Register Celery Beat schedules (django-celery-beat DB)
# ========
setup_celery_beat_schedules() {
  echo "[entrypoint] Ensuring Celery Beat cleanup schedule ..."
  python - <<'PY'
import os

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.environ.get("DJANGO_SETTINGS_MODULE", "redartdigital.settings.docker"),
)
django.setup()

from django_celery_beat.models import CrontabSchedule, PeriodicTask

schedule, _ = CrontabSchedule.objects.get_or_create(
    minute="0",
    hour="0",
    day_of_week="*",
    day_of_month="*",
    month_of_year="*",
    timezone="UTC",
)

PeriodicTask.objects.update_or_create(
    name="cleanup-celery-storage-every-24h",
    defaults={
        "crontab": schedule,
        "interval": None,
        "task": "redartdigital.tasks.cleanup_celery_storage",
        "enabled": True,
        "description": "Flush Celery Redis result storage every 24 hours (00:00 UTC).",
    },
)
print("[entrypoint] Beat schedule ready: cleanup-celery-storage-every-24h")
PY
}

ROLE="${1:-web}"

# ========
# Shared startup
# ========
wait_for_postgres
wait_for_redis

# ========
# Django migrate + static + beat schedules (web only)
# ========
if [[ "${ROLE}" == "web" ]]; then
  echo "[entrypoint] Running migrations ..."
  python manage.py migrate --noinput
  setup_celery_beat_schedules
  echo "[entrypoint] Collecting static files ..."
  python manage.py collectstatic --noinput
fi

# ========
# Launch role
# ========
case "${ROLE}" in
  web)
    echo "[entrypoint] Starting Gunicorn ..."
    exec gunicorn redartdigital.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-120}"
    ;;
  worker)
    echo "[entrypoint] Starting Celery worker ..."
    exec celery -A redartdigital worker \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
      --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    echo "[entrypoint] Starting Celery beat ..."
    exec celery -A redartdigital beat \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
      --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  shell)
    exec python manage.py shell
    ;;
  *)
    echo "[entrypoint] Unknown role: ${ROLE}"
    echo "Usage: entrypoint.sh [web|worker|beat|shell]"
    exit 1
    ;;
esac
