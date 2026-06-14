# crawler-worker平台化监控_Codex自测报告

更新时间：2026-06-14 18:50 CST

## 1. 本次修改目标

将 crawler-worker 从“只能手动触发采集”的独立容器，增强为可被 PC 后台监控和维护的采集平台入口。重点解决任务状态不可见、浏览器进程残留不可操作、连续失败缺少熔断、单任务缺少统一超时的问题。

## 2. 修改文件列表

- `scripts/crawler_worker.py`
- `controllers/admin.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/views/netdisk/ops-center.vue`

## 3. 核心实现说明

- worker 新增 `/status`，返回 worker 在线状态、浏览器进程数、进程上限、任务超时、运行中任务、熔断任务、每个采集任务的最近运行结果。
- worker 新增 `/maintenance/cleanup-browsers`，支持手动清理 Chromium / Playwright 残留进程。
- worker 手动任务增加统一超时、运行中拦截、连续失败计数和失败熔断冷却。
- 主后端 `/admin/netdisk/crawlers/status` 会代理 worker 状态，PC 后台无需直连 worker。
- 主后端新增 `/admin/netdisk/crawlers/maintenance/cleanup-browsers`，仅主管角色可触发。
- PC 后台待处理中心展示 worker 在线/离线、浏览器进程数、运行中任务、熔断任务、每个采集任务状态，并提供清理浏览器进程按钮。

## 4. 已运行测试

| 测试项 | 命令 | 结果 |
|---|---|---|
| 后端关键文件静态编译 | `python3 -m py_compile scripts/crawler_worker.py controllers/admin.py core/browser_guard.py` | 通过 |
| 后端目录静态编译 | `python3 -m compileall controllers scripts core -q` | 通过 |
| PC 后台构建 | `npm run build`（目录：`adminVideo`） | 通过 |

## 5. 测试结果

- 后端 Python 语法检查通过。
- PC 后台 TypeScript 检查和生产构建通过。
- 构建存在第三方依赖注释和大包体积提示，不阻断功能。

## 6. 未覆盖测试项

- 未在本机执行 Docker 容器内真实 worker 验证，因为本机没有 `docker` / `podman` / `colima` 命令。
- 未实际触发生产 worker 采集任务，避免用服务器旧容器验证本地未部署代码。
- 未验证生产机 Docker 层面的自动重启 worker；本次没有引入从 app 容器直接重启另一个容器的能力，避免挂载 Docker socket 带来额外风险。

## 7. 可能影响范围

- PC 后台待处理中心的资源采集任务面板。
- 主后端后台 crawler 状态与手动采集接口。
- crawler-worker 手动采集任务执行链路。

## 8. 需要 AI 测试官复核的事项

- 部署后在容器环境执行 worker `/status`、`/health`、`/maintenance/cleanup-browsers`。
- 在 PC 后台确认 worker 在线状态、浏览器进程数、最近任务状态展示正确。
- 手动触发 KDocs / LinuxDo 采集，确认成功、失败、超时、连续失败熔断均符合预期。
- 检查浏览器残留进程是否能被自动清理和手动清理。

