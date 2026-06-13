# crawler-worker 独立化 Codex 自测报告

更新时间：2026-06-14

## 1. 本次修改目标

把浏览器采集从主后端拆到独立 `crawler-worker` 容器，降低主后端部署负担，并避免采集异常影响小程序和后台主接口。

## 2. 修改文件列表

| 文件 | 说明 |
|---|---|
| `Dockerfile` | 拆分主后端 runtime 和 crawler runtime |
| `docker-compose.yml` | 新增 `crawler-worker` 服务 |
| `main.py` | 主后端不再启动 KDocs / LinuxDo 采集定时任务 |
| `controllers/admin.py` | 后台手动采集改为转发到 worker |
| `scripts/crawler_worker.py` | 新增 worker FastAPI 服务 |
| `docs/crawler-worker/README.md` | worker 总说明 |
| `docs/crawler-worker/采集规则说明.md` | 采集规则说明 |
| `docs/crawler-worker/PC导入与服务器入库流程.md` | PC 导入兜底流程 |
| `docs/crawler-worker/故障处理.md` | 故障排查说明 |
| `docs/crawler-worker/后续拆仓建议.md` | 后续独立仓库建议 |

## 3. 核心实现说明

- 主后端容器不再安装 Chromium。
- 采集 worker 单独安装 Chromium。
- 主后端只保留积分、质量统计、7 天奖励等核心定时任务。
- KDocs / LinuxDo 采集定时任务转移到 worker。
- PC 后台手动采集请求先到主后端，再由主后端转发给 worker。
- 主后端不依赖 worker 健康才能启动。

## 4. 已运行测试

| 测试 | 结果 |
|---|---|
| `python3 -m py_compile main.py controllers/admin.py scripts/crawler_worker.py` | 通过 |
| `git diff --check` | 通过 |
| 服务器构建主后端镜像 | 通过 |
| 服务器构建 crawler-worker 镜像 | 通过 |
| 主后端容器健康检查 | 通过 |
| crawler-worker 容器健康检查 | 通过 |
| 后台采集状态接口 | 通过 |

## 5. 测试结果

服务器当前状态：

| 容器 | 镜像 | 状态 |
|---|---|---|
| `video-service-app` | `pythonvideo-app:stage2-5805616` | healthy |
| `video-service-crawler-worker` | `pythonvideo-crawler:stage2-5805616` | healthy |

健康检查：

```json
{"status":"ok","service":"crawler-worker","chromium":"/usr/bin/chromium"}
```

## 6. 未覆盖测试项

- 未在生产环境直接触发真实采集，避免立刻写入新资源数据。
- 未验证 LinuxDo 在服务器网络下是否可访问。
- 未验证旧视频解析功能是否仍依赖 Chromium。

## 7. 可能影响范围

- 后台手动采集。
- KDocs / LinuxDo 定时采集。
- 旧视频解析中任何依赖浏览器的功能。

## 8. 需要人工确认的地方

- 是否在 PC 后台手动触发一次 KDocs 小批量采集。
- LinuxDo 是否继续走服务器采集，还是优先走 PC 导出文件导入。
- worker 稳定运行一周后，是否拆成独立 Git 仓库。

