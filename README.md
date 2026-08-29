# RedArt EDI Backend

Django REST microservice for **Colorado Medicaid NEMT** electronic claim submission (HIPAA **X12 837P**).

Built for [RedArt Digital](https://redartdigital.com/) — trip/claim data in, standards-based EDI batches out. This service will later connect to Colorado HCPF via MFT/SFTP ([EDI Support](https://hcpf.colorado.gov/edi-support)).

## Stack

- **Django 5.2 LTS** + **Django REST Framework**
- **PostgreSQL** (Docker) / SQLite (local bootstrap only)
- **Celery** + **Celery Beat** + **Redis**
- **Gunicorn**, **Docker Compose**
- OpenAPI docs via **drf-spectacular**

## Project status

**Done:** project scaffold, settings, health API, Swagger, Celery/Beat/Redis, Docker, daily Redis result cleanup.

**Next:** billing profiles, claim validation, 837P generation, batching, file naming, then SFTP + 999/835.

## Quick start (Docker)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env
./scripts/start.sh
# or: docker compose up --build -d
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/api/health/ | Health check |
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/admin/ | Django admin |

```bash
./scripts/start.sh logs    # follow logs
./scripts/start.sh down    # stop stack
```

Compose starts: **Postgres**, **Redis**, **web**, **Celery worker**, **Celery beat**.  
Web container runs migrations on startup.

## Local development (without Docker)

```bash
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Celery (needs Redis running):

```bash
celery -A redartdigital worker -l INFO
celery -A redartdigital beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Settings

| Module | Use |
|--------|-----|
| `redartdigital.settings.local` | Local runserver |
| `redartdigital.settings.docker` | Docker Compose |
| `redartdigital.settings.production` | Production |

Copy `.env.example` → `.env`. Never commit `.env`.

## Celery storage

- **Broker / results:** Redis (not SQLite)
- **Daily cleanup:** Beat runs `cleanup_celery_storage` at 00:00 UTC (flushes Redis result DB only)

## Repo

https://github.com/ayazkhan1410/RedArt-EDI-Backend

## License

Proprietary — RedArt LLC. All rights reserved.
