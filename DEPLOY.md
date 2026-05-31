# 服务器部署操作指南

---

## 前置条件

- 服务器 IP: `81.70.84.35`
- SSH 用户: `root` 或 `ubuntu`
- 项目路径: 假设放在 `/opt/video-service/`（按你实际情况调整）

---

## 零、一次性配置：Docker Hub 镜像加速（仅需一次）

```bash
# 在服务器上执行，之后 docker pull 会走清华镜像
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://docker.1ms.run"]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

> `docker.1ms.run` 是目前可用的 Docker Hub 代理。如果挂了，换 `https://mirror.ccs.tencentyun.com`（腾讯云）、`https://hub-mirror.c.163.com`（网易）。

---

## 一、拉取最新代码

```bash
ssh root@81.70.84.35
cd /opt/video-service
git pull origin master
```

---

## 二、确保 .env 配置正确

`.env` 不会被 Git 跟踪，服务器上的 `.env` 不会受影响。确认以下变量存在且正确：

```bash
vim /opt/video-service/.env
```

**需确认的环境变量：**

| 变量名 | 说明 | 服务器建议值 |
|--------|------|-------------|
| `DATABASE_URL` | PostgreSQL 连接 | `postgresql+asyncpg://postgres:你的密码@postgres:5432/agent` |
| `REDIS_URL` | Redis 连接 | `redis://redis:6379/0` |
| `NOTIFY_URL` | 微信支付回调 | `https://api.lifelove.top/wxpay/api/pay/notify` |
| `DOMAIN` | 域名 | `api.lifelove.top` |
| `CORS_ORIGINS` | 跨域白名单 | `https://api.lifelove.top,https://www.lifelove.top` |
| `DB_ECHO` | SQL 调试 | `false` |
| `DB_SSL_MODE` | SSL 模式 | `prefer` |
| `DB_PASSWORD` | 数据库密码 | docker-compose.yml 引用此变量 |

> **重要：`DATABASE_URL` 的 host 必须是 `postgres`（容器名），不是 `127.0.0.1`。**

---

## 三、重建并重启（利用 Docker 层缓存，不动的不重下）

```bash
cd /opt/video-service

# 构建（不用 --no-cache，Docker 层缓存会复用未变更的层）
# ffmpeg 层在 COPY . . 之前，代码改了也不重新下载
docker compose build app

# 重启
docker compose up -d

# 看日志确认
docker compose logs -f app --tail 50
```

**缓存解释：**

```
Dockerfile 层顺序          每次代码变更后？
────────────────────────────────────────
apt 镜像配置              ✅ 缓存复用（不重跑）
ffmpeg + 系统库安装       ✅ 缓存复用（不重下）
COPY --from=builder venv  ✅ 缓存复用（pyproject.toml 不变）
COPY . .                  ❌ 代码变 → 此层及之后重新构建
mkdir + useradd           重新跑（很快）
playwright install        重新跑（但浏览器二进制在 Docker 层缓存里，增量下载）
```

> 只有 `pyproject.toml` / `uv.lock` 变了，uv sync 层才会重建。平时改代码只重建 COPY 之后的层。

> 如果 `cookies.txt.dan` 在服务器上不存在，先在 `docker-compose.yml` 里注释对应行。

---

## 四、数据库迁移（如有表结构变更）

```bash
docker compose exec app alembic upgrade head
docker compose exec app alembic current
```

---

## 五、验证

```bash
curl http://localhost:8000/health
# 应返回: {"status":"ok","message":"服务运行正常"}
```

---

## 六、关键变更说明

### Dockerfile

1. `uv sync --frozen` 替代 `uv pip compile`，lockfile 精确安装
2. 清华 APT 镜像源（apt 包走清华，pip 包也走清华）
3. ffmpeg 等系统依赖放在 COPY . . 之前，利用 Docker 层缓存

### docker-compose.yml

- **移除了 `./:/app` 整项目挂载**，代码由 Docker 镜像决定
- 只挂载数据目录：image/downloads/logs/certs/cookies.txt/.env

### 安全

- `alembic.ini` 和 `migrations/env.py` 的硬编码密码已清除
