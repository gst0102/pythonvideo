# 爬虫定时与历史回补规则 Codex 自测报告

## 1. 本次修改目标

- 明确 4 个资源来源的采集频率、每次数量和入库策略。
- LinuxDo 支持从 2026-01-01 到当前日期的历史回补。
- 日常定时任务每次只抓前 20 条，避免服务器压力过大。
- 采集结束后关闭页面、上下文和浏览器，并接入浏览器守护，避免浏览器残留堆积。

## 2. 修改文件列表

- `core/kdocs_service.py`
- `services/sync_service.py`
- `services/linuxdo_resource_service.py`
- `scripts/linuxdo_netdisk_sync.py`
- `scripts/verify_linuxdo_hybrid_classification.py`
- `main.py`
- `docs/yuexiang-stage2-docs/12-linuxdo-hybrid-classification-sync.md`

## 3. 核心实现说明

- KDocs 同步增加最新日期分组过滤：有日期分组时只取最新日期下的资源，最多 20 条；不足 20 条不补旧数据。
- KDocs 影视剧/番剧同步频率从 15 分钟调整为 60 分钟。
- KDocs 电影和 4K 仍在每天 00:00 同步，每次每来源前 20 条。
- LinuxDo 日常同步改为每 12 小时一次，每次前 20 条。
- LinuxDo 采集支持 `since_date`、`until_date` 和 `limit`，并新增 `backfill` 命令，默认回补 `2026-01-01` 到当天。
- LinuxDo Playwright 采集接入 `browser_slot`、`chromium_launch_args`，并在 `finally` 中关闭 page、context、browser。

## 4. 已运行测试

- `python3 -m py_compile core/kdocs_service.py services/sync_service.py services/linuxdo_resource_service.py scripts/linuxdo_netdisk_sync.py scripts/verify_linuxdo_hybrid_classification.py`
- Codex runtime Python 执行同样的 `py_compile`

## 5. 测试结果

- Python 静态编译通过。
- `scripts/verify_kdocs_netdisk_sync.py` 未能在当前 macOS 环境完成：缺少 `httpx`。
- `scripts/verify_linuxdo_hybrid_classification.py` 未能在当前 macOS 环境完成：缺少 `sqlalchemy/sqlmodel`。
- 项目 `.venv` 是 Windows 结构，当前 macOS 不能直接执行；本机也没有 `uv` 命令。

## 6. 未覆盖测试项

- 未实际运行 LinuxDo 2026-01-01 至今的历史回补入库。
- 未实际打开 Playwright 抓取 LinuxDo/KDocs。
- 未在服务器环境验证 APScheduler 真实触发。

## 7. 可能影响范围

- KDocs 影视资源同步数量从全量变为“最新日期分组最多 20 条”。
- LinuxDo 定时任务从每日一次变为每 12 小时一次。
- 服务器浏览器并发默认仍受 `BROWSER_AUTOMATION_CONCURRENCY=1` 控制。

## 8. 需要人工确认的地方

- LinuxDo 历史回补建议在服务器低峰期手动执行，并观察自动入库、跳过重复、待审核数量。
- 如果 KDocs 文档没有清晰日期分组，会退回解析结果前 20 条；建议维护文档时保留日期行。
