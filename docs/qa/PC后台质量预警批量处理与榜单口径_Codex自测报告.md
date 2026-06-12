# PC 后台质量预警批量处理与榜单口径_Codex自测报告

## 1. 本次修改目标

- 支持质量预警批量已读、批量忽略、批量已处理。
- 运营看板在质量统计任务失败时顶部明显提醒。
- 资源质量榜支持今日、最近 7 日、全历史口径切换。
- 高风险质量预警进入待复核口径，供运营集中处理。

## 2. 修改文件列表

- `controllers/admin.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/views/dashboard/index.vue`
- `adminVideo/src/views/netdisk/quality-alerts.vue`
- `docs/qa/PC后台质量预警批量处理与榜单口径_Codex自测报告.md`

## 3. 核心实现说明

- 后端 `GET /admin/netdisk/ops-dashboard` 增加 `quality_range` 参数，返回质量榜口径、统计任务运行状态和待复核数量。
- 后端 `GET /admin/netdisk/resource-quality` 增加 `range=today|7d|all`，优先读取每日统计表并按时间范围聚合。
- 后端新增 `POST /admin/netdisk/resource-quality/alerts-batch/{action}`，支持 `read/resolve/ignore` 批量处理，并记录审核日志。
- 质量预警返回 `in_review_pool` 和 `review_state`，`open/read` 统一视为待复核池。
- PC 看板增加质量统计失败提醒和质量榜口径切换。
- 预警列表增加多选、批量已读、批量已处理、批量忽略。

## 4. 已运行测试

- 后端 Python 语法检查。
- 后端质量榜今日 / 7 日 / 全历史接口检查。
- 后端运营看板接口检查。
- 后端质量预警批量处理接口检查。
- PC 后台 `npm run build`。
- PC 后台页面基础浏览器验收。

## 5. 测试结果

- 后端 Python 语法检查通过。
- 质量榜 `range=today`、`range=7d`、`range=all` 均返回 200，并返回对应 `range` 字段。
- 运营看板 `quality_range=all` 返回 200，并返回 `quality_stats_runtime`、`quality_review_pool`、`resource_quality_rankings`。
- 质量预警批量已读接口返回 200，单条演示预警成功从 `open` 更新为 `read`，并保留 `in_review_pool=true`。
- 质量统计任务运行状态接口返回 `status=success`；本地未模拟失败状态。
- PC 后台 `npm run build` 通过。
- 内置浏览器验收通过：运营看板可见“资源质量榜 / 今日 / 7日 / 全历史”，预警页可见“批量已读 / 批量已处理 / 批量忽略 / 已选”。

## 6. 未覆盖测试项

- 未做大数据量下每日统计表性能压测。
- 未做多管理员同时批量处理同一预警的并发一致性测试。
- 未接入真实定时任务失败通知渠道，只在后台看板展示失败提醒。

## 7. 可能影响范围

- PC 运营看板资源质量榜。
- PC 质量预警列表。
- 后端网盘资源质量聚合与预警处理接口。

## 8. 需要 AI 测试官复核的事项

- 批量处理是否满足运营人员追责和回溯要求。
- 待复核池口径是否需要独立页面或独立状态表。
- 全历史质量榜在资源量继续增长后是否需要完全依赖离线统计表。
