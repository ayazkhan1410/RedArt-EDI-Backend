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
# ========
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
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

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["web"]
