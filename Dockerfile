# ========
# Python base image
# ========
FROM python:3.12-slim-bookworm

# ========
# Environment
# ========
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ========
# System packages
# (Check-Valid-Until=false avoids Docker Desktop clock-skew apt failures)
# psycopg[binary] does not need libpq-dev / build-essential
# ========
RUN apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update \
    && apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false install -y --no-install-recommends \
        curl \
        bash \
    && rm -rf /var/lib/apt/lists/*

# ========
# App directory
# ========
WORKDIR /app

# ========
# Python dependencies
# ========
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt

# ========
# Project source
# ========
COPY . /app

# ========
# Entrypoint
# ========
RUN chmod +x /app/scripts/entrypoint.sh /app/scripts/start.sh

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "/app/scripts/entrypoint.sh"]
CMD ["web"]

