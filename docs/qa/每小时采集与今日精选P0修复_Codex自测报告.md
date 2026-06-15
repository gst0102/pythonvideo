# 每小时采集与今日精选P0修复_Codex自测报告

## 1. 本次修改目标

优先处理内容产品核心 P0：确认 KDocs 每小时采集真实运行，并修复采集报告“本次精选预览前三条”和首页今日精选口径不一致的问题。

## 2. 修改文件列表

- `myproject/services/netdisk_resource_service.py`
- `myproject/core/timezone.py`
- 生产 worker 容器补齐模型文件：
  - `models/netdisk_unlock_hidden.py`
  - `models/netdisk_resource_subscription.py`
  - `models/netdisk_resource_subscription_push_log.py`
  - `models/netdisk_crawler_run.py`
  - `models/__init__.py`

## 3. 核心处理

- 确认线上 `video-service-crawler-worker` 存活且调度任务存在。
- 确认 `kdocs_anime` 每小时 30 分执行，最近成功时间为北京时间 01:40 左右的手动验证运行。
- 修复 worker 容器代码落后于主 API 容器的问题，同步 `NetdiskResourceService` 和时间口径代码。
- 补齐 worker 容器缺失模型文件，否则新服务代码运行会报 `No module named 'models.netdisk_unlock_hidden'`。
- 手动触发 `kdocs_anime`，确认采集成功并写入新运行历史。

## 4. 验证结果

- `POST /run/kdocs_anime` 成功返回 `synced=20`、`fetched=20`。
- worker 最新 `featured_preview` 前三条：
  - `哈哈哈哈哈 第六季.HD4K更 6.15期`
  - `喜欢你我也是 第六季.HD4K更 6.15期`
  - `无限超越班 第四季.HD4K更6.15期`
- 线上首页今日精选接口 `GET /netdisk/resources/featured-today?limit=3` 返回同一批前三条。
- worker 状态 `running_tasks=[]`、`blocked_tasks=[]`，无熔断。
- 下一次自动采集时间：北京时间 `2026-06-16 02:30`。

## 5. 已发现并修复的问题

- 问题：主 API 容器已是新代码，但 crawler-worker 容器仍是旧代码，导致运行历史里的“本次精选预览”继续使用旧口径。
- 问题：同步新服务代码后，worker 缺少新增模型文件，手动采集出现 500。
- 修复：将主 API 相关服务和模型文件同步到 worker 容器并重启，重新手动运行采集验证。

## 6. 未覆盖风险

- 这次是生产热更新，没有重建 crawler-worker 镜像；后续正式部署时需要重建镜像，避免容器重建后丢失热更新文件。
- 需要观察北京时间 02:30 的自动运行是否继续成功。

## 7. 下一步建议

- 把 crawler-worker 镜像重新 build 一次，固化本次热更新文件。
- 在 PC 后台采集面板增加明显告警：如果 worker 代码运行失败或最近一次失败，顶部直接红色提示。
