# ========================================
# Stage 1: build dependencies with uv lockfile
# ========================================
FROM python:3.10-slim-bookworm AS builder

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /build

# Speed up Debian package downloads for China-based hosts.
RUN sed -i 's|http://deb.debian.org|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the locked dependency manifest first so dependency installation stays cached.
COPY requirements.lock.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /build/.venv \
    && /build/.venv/bin/pip install --upgrade pip \
    && /build/.venv/bin/pip install --require-hashes -r requirements.lock.txt \
    && /build/.venv/bin/python --version

COPY . .

RUN /build/.venv/bin/uvicorn --version


# ========================================
# Stage 2: runtime image
# ========================================
FROM python:3.10-slim-bookworm AS runtime

ARG APP_VERSION=dev
ARG VCS_REF=local
ARG BUILD_DATE=unknown
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
ARG PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=1200000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST} \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=${PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT}

WORKDIR /app

LABEL org.opencontainers.image.title="pythonvideo-app" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"

RUN sed -i 's|http://deb.debian.org|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# Runtime system packages for ffmpeg and Playwright Chromium.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/.venv /app/.venv

# Rewrite console-script shebangs after copying the venv from /build to /app.
RUN find /app/.venv/bin -maxdepth 1 -type f -exec \
    sed -i '1s|^#!/build/.venv/bin/python.*$|#!/app/.venv/bin/python|' {} + \
    && /app/.venv/bin/uvicorn --version

COPY . .

RUN mkdir -p /app/image /app/downloads /app/logs /app/certs /home/appuser \
    && echo 'appuser:x:1000:1000::/home/appuser:/bin/sh' >> /etc/passwd \
    && echo 'appuser:x:1000:' >> /etc/group \
    && chown -R 1000:1000 /app /home/appuser

USER 1000:1000

RUN python -m playwright install chromium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
