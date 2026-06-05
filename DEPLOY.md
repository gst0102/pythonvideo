# 部署说明

最后更新：2026-06-05

## 适用范围

当前线上环境按以下信息为准：

- 服务器 IP：`81.70.84.35`
- SSH 用户：`ubuntu`
- 后端目录：`/opt/pythonvideo`
- PC 管理端目录：`/opt/pc-frontend`
- 后端正式发布分支：`feature/yuexiang-stage2-mvp`
- PC 管理端分支：`main`

如果历史文档与这里不一致，以服务器实际目录和当前仓库状态为准。

## 当前部署原则

后端从现在开始不再依赖“容器内热同步代码”作为常规发布手段。

标准流程应为：

1. 基于 Git 提交构建正式镜像
2. 给镜像打明确 tag
3. 生产环境只拉镜像并重建容器
4. 发布后执行 Alembic 迁移和健康检查

推荐镜像 tag 格式：

```text
pythonvideo-app:stage2-<git-sha>
```

例如：

```text
pythonvideo-app:stage2-7070f9e
```

## 本地 / 构建机构建

进入仓库：

```bash
cd /opt/pythonvideo
git fetch origin
git checkout feature/yuexiang-stage2-mvp
git pull --ff-only origin feature/yuexiang-stage2-mvp
```

设置本次镜像变量：

```bash
export APP_IMAGE=pythonvideo-app:stage2-7070f9e
export APP_VERSION=stage2-7070f9e
export VCS_REF=7070f9e
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

构建镜像：

```bash
docker compose build app
docker image inspect "$APP_IMAGE"
```

如果要推送到镜像仓库，先按团队实际仓库地址重新打 tag，例如：

```bash
docker tag "$APP_IMAGE" registry.example.com/pythonvideo-app:stage2-7070f9e
docker push registry.example.com/pythonvideo-app:stage2-7070f9e
```

## 生产环境发布

### 1. 登录并确认仓库状态

```bash
ssh ubuntu@81.70.84.35
cd /opt/pythonvideo
git status --short
git branch --show-current
git rev-parse --short HEAD
```

如果服务器工作区有本地脏改动，不要直接覆盖，先确认来源。

### 2. 使用明确镜像 tag

生产环境建议通过环境变量指定镜像：

```bash
export APP_IMAGE=pythonvideo-app:stage2-7070f9e
export APP_VERSION=stage2-7070f9e
export VCS_REF=7070f9e
export BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

如果镜像来自远端仓库，先拉取：

```bash
docker pull "$APP_IMAGE"
```

### 3. 重建应用容器

```bash
cd /opt/pythonvideo
docker compose up -d --no-build app
docker compose exec -T app alembic upgrade head
docker compose exec -T app alembic current
```

### 4. 发布后检查

```bash
curl -s http://localhost:8000/health
curl -i -s http://localhost:8000/game/tasks/status
curl -i -s http://localhost:8000/admin/ad/game-bonus-config
docker compose ps
docker compose logs --tail=100 app
```

健康检查应返回：

```json
{"status":"ok","message":"服务运行正常"}
```

## docker-compose 改造说明

当前 `docker-compose.yml` 已支持以下发布方式：

### 方式 A：本地直接构建

```bash
export APP_IMAGE=pythonvideo-app:stage2-7070f9e
export APP_VERSION=stage2-7070f9e
export VCS_REF=7070f9e
docker compose build app
docker compose up -d app
```

### 方式 B：只使用预构建镜像

```bash
export APP_IMAGE=pythonvideo-app:stage2-7070f9e
docker compose up -d --no-build app
```

`docker-compose.yml` 中 `app` 服务已经显式声明：

- `image: ${APP_IMAGE:-pythonvideo-app:stage2-local}`
- `build.target: runtime`
- `build.args.APP_VERSION`
- `build.args.VCS_REF`
- `build.args.BUILD_DATE`

这意味着：

1. 同一套 compose 既能构建，也能使用外部已构建镜像
2. 生产环境不再需要依赖 `pythonvideo-app:latest`
3. 镜像版本和 Git 提交可以直接对应

## Dockerfile 改造说明

当前 `Dockerfile` 已做以下收敛优化：

1. 使用多阶段构建，运行镜像只保留必要产物
2. 先复制 `pyproject.toml` 和 `uv.lock`，让依赖层尽量命中缓存
3. `uv sync` 使用缓存挂载，减少重复下载
4. 注入 `APP_VERSION` / `VCS_REF` / `BUILD_DATE` OCI 标签
5. 保留 Playwright Chromium 安装，但不再让普通代码改动频繁击穿依赖层缓存

## Alembic 注意事项

数据库名仍然是：

```text
agent
```

检查数据库时使用：

```bash
docker compose exec -T postgres psql -U postgres -d agent
```

迁移完成后确认：

```bash
docker compose exec -T app alembic current
```

## 不推荐的做法

以下方式只适合应急救火，不适合作为后续正式升级流程：

1. 直接把代码复制进正在运行的容器
2. 继续依赖旧 `pythonvideo-app:latest`
3. 在生产机上长时间反复试构建但不固定镜像版本
4. 不记录镜像 tag 就直接重启服务

## 回滚建议

如果新镜像发布异常，优先按“旧镜像 tag + 旧 Git 分支”回退：

```bash
cd /opt/pythonvideo
git checkout backup/prod-pre-stage2-20260605
export APP_IMAGE=<previous-stable-image>
docker compose up -d --no-build app
```

如果只是业务代码问题，但镜像可用，也可以只把 `APP_IMAGE` 切回上一个稳定 tag。

## 当前已知生产基线

- 生产仓库分支：`feature/yuexiang-stage2-mvp`
- 生产仓库基线提交：`5ae17ec`
- 生产回退分支：`backup/prod-pre-stage2-20260605`
- 当前真实广告位：
  - `adunit-e66ca7039925b740`
  - `adunit-7c61b0922792ddc9`
  - `adunit-a921c4e0383a451f`

后续每次正式发布后，都应把本文件里的“当前已知生产基线”同步到最新 tag 和提交号。
