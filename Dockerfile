# ========================================
# 阶段1: 构建依赖 (uv sync from lockfile)
# ========================================
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# 清华 APT 镜像源（加速 ffmpeg 等包下载）
RUN sed -i 's|http://deb.debian.org|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 安装编译工具 + uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制完整源码 — uv sync 安装项目 + 所有依赖（确保 uvicorn console script 正确创建）
COPY . .

RUN uv sync --frozen --no-dev \
    && /build/.venv/bin/uvicorn --version


# ========================================
# 阶段2: 生产镜像 (最小化)
# ========================================
FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"

WORKDIR /app

# 清华 APT 镜像源
RUN sed -i 's|http://deb.debian.org|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 运行时系统依赖：ffmpeg + Playwright Chromium 运行库
# 此层在 COPY . . 之前，代码变更不会导致重复下载
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

# uv 在 builder 的 /build 下生成 console scripts，复制到 /app 后需要修正 shebang。
RUN find /app/.venv/bin -maxdepth 1 -type f -exec \
    sed -i '1s|^#!/build/.venv/bin/python.*$|#!/app/.venv/bin/python|' {} + \
    && /app/.venv/bin/uvicorn --version

# 复制应用代码（此层及之后会因代码变更重新构建）
COPY . .

# 创建运行时目录 & 非 root 用户
# 不依赖 useradd/passwd 包 — 直接写 /etc/passwd & /etc/group，任何 slim 镜像都可用
RUN mkdir -p /app/image /app/downloads /app/logs /app/certs /home/appuser \
    && echo 'appuser:x:1000:1000::/home/appuser:/bin/sh' >> /etc/passwd \
    && echo 'appuser:x:1000:' >> /etc/group \
    && chown -R 1000:1000 /app /home/appuser

USER 1000:1000

# 安装 Playwright Chromium 浏览器 (必须以 appuser 运行)
RUN python -m playwright install chromium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
