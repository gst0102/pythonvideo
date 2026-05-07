FROM python:3.10-slim

LABEL maintainer="your-email@example.com"
LABEL description="FastAPI Video Download Service with WeChat Pay"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY uv.lock ./

RUN pip install --upgrade pip && \
    pip install uv && \
    uv pip install --system -r <(uv pip compile pyproject.toml)

COPY . .

RUN mkdir -p /app/image /app/downloads /app/logs /app/certs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
