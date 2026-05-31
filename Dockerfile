# ========================================
# 阶段1: 构建依赖 (uv sync from lockfile)
# ========================================
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# 安装编译工具 + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 先复制依赖文件，利于 Docker 缓存
COPY pyproject.toml uv.lock ./

# 用 lockfile 精确安装（跳过项目本身，后面 COPY . 会带进来）
RUN uv sync --frozen --no-dev --no-install-project


# ========================================
# 阶段2: 生产镜像 (最小化)
# ========================================
FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"

WORKDIR /app

# 运行时系统依赖：ffmpeg + Playwright Chromium 运行库
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

# 从构建阶段复制虚拟环境
COPY --from=builder /build/.venv /app/.venv

# 复制应用代码
COPY . .

# 创建运行时目录
RUN mkdir -p /app/image /app/downloads /app/logs /app/certs \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

# 安装 Playwright Chromium 浏览器 (必须以 appuser 运行)
RUN python -m playwright install chromium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
