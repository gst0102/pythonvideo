# ========================================
# 阶段1: 构建环境 (包含构建工具)
# ========================================
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/sbin:/root/.local/bin"

WORKDIR /build

# 使用阿里云镜像源
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

# 使用 pip 安装 uv（官方脚本可能被墙，用 pip 更稳定）
RUN pip install uv --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

COPY pyproject.toml uv.lock ./

RUN uv pip compile pyproject.toml -o /tmp/requirements.txt \
    && uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.txt


# ========================================
# 阶段2: 生产环境 (最小化运行时镜像)
# ========================================
FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/sbin"

WORKDIR /app

# 使用阿里云镜像源
RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi

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

COPY --from=builder /opt/venv /opt/venv

RUN /opt/venv/bin/playwright install --with-deps chromium \
    && /opt/venv/bin/playwright install-deps chromium

COPY . .

RUN mkdir -p /app/image /app/downloads /app/logs /app/certs \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app /opt/venv

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
