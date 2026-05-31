# 服务器部署操作指南

> 本文档供服务器手动操作使用，不需要提交到 Git（已加入 .gitignore）。

---

## 前置条件

- 服务器 IP: `81.70.84.35`
- SSH 用户: `root` 或 `ubuntu`
- 项目路径: 假设放在 `/opt/video-service/`（按你实际情况调整）

---

## 一、拉取最新代码

```bash
ssh root@81.70.84.35
cd /opt/video-service    # 或你的实际项目路径
git pull origin master
```

---

## 二、确保 .env 配置正确

`.env` 不会被 Git 跟踪，服务器上的 `.env` 不会受影响。但新增了一些环境变量，需要确认：

```bash
# 编辑服务器上的 .env，确认以下变量存在且正确：
vim /opt/video-service/.env
```

**本次新增/需确认的变量：**

| 变量名 | 说明 | 服务器建议值 |
|--------|------|-------------|
| `DATABASE_URL` | PostgreSQL 连接 | `postgresql+asyncpg://postgres:你的密码@postgres:5432/agent` |
| `REDIS_URL` | Redis 连接 | `redis://redis:6379/0` |
| `NOTIFY_URL` | 微信支付回调 | `https://api.lifelove.top/wxpay/api/pay/notify` |
| `DOMAIN` | 域名 | `api.lifelove.top` |
| `CORS_ORIGINS` | 跨域白名单 | `https://api.lifelove.top,https://www.lifelove.top` |
| `DB_ECHO` | SQL 调试（生产关） | `false` |
| `DB_SSL_MODE` | SSL 模式 | `prefer` |
| `ANIME_SYNC_ENABLED` | 番剧同步开关 | `true` |
| `ANIME_SYNC_INTERVAL` | 同步间隔(分钟) | `15` |
| `DB_PASSWORD` | 数据库密码 | 你实际的密码（docker-compose 引用） |

**注意：`DATABASE_URL` 必须使用容器内的 hostname `postgres`，不是 `127.0.0.1` 或 `localhost`。**

---

## 三、重建并重启服务

```bash
cd /opt/video-service

# 1. 拉取新镜像 + 重新构建 app 服务
docker compose build --no-cache app

# 2. 重启所有服务
docker compose up -d

# 3. 查看日志确认正常
docker compose logs -f app --tail 50
```

> 如果 `cookies.txt.dan` 文件在服务器上不存在，先在 `docker-compose.yml` 中注释掉对应行。

---

## 四、数据库迁移（如有表结构变更）

```bash
# 进入 app 容器执行迁移
docker compose exec app alembic upgrade head

# 确认版本
docker compose exec app alembic current
```

---

## 五、验证

```bash
# 健康检查
curl http://localhost:8000/health

# 应该返回:
# {"status":"ok","message":"服务运行正常"}
```

---

## 六、重要变更说明

### 本次 Dockerfile 改动

1. 改用 `uv sync --frozen` 替代 `uv pip compile`，从 lockfile 精确安装依赖
2. 使用 `UV_LINK_MODE=copy` 确保 venv 可跨 stage 复制
3. Playwright Chromium 浏览器安装步骤不变

### 本次 docker-compose.yml 改动

**关键：移除了 `./:/app` 的整项目挂载。** 
- 之前：整个项目目录挂载到容器内，会覆盖 Docker 镜像中的文件
- 现在：只挂载数据目录（image/downloads/logs/certs/cookies.txt/.env）
- **好处**：Docker 镜像构建的代码优先，不会出现"改了 Dockerfile 但容器跑的仍是旧代码"的问题
- **开发调试**：如需热重载，可创建 `docker-compose.override.yml`：

```yaml
# docker-compose.override.yml（本地开发用，不要提交到 Git）
services:
  app:
    volumes:
      - ./:/app
      - /app/__pycache__
      - /app/.venv
```

### 安全修复

- `alembic.ini` 和 `migrations/env.py` 中的硬编码密码已移除，改为从 `DATABASE_URL` 环境变量读取
