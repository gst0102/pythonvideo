# PC后台日志导出积分来源与待追缴处理_Codex自测报告

## 1. 本次修改目标

- 操作日志支持日期筛选。
- 操作日志支持 CSV 导出。
- 运营看板增加今日积分来源分布。
- 待追缴支持后台处理：追缴扣除、人工关闭。

## 2. 修改文件列表

后端：

- `controllers/admin.py`

PC 后台：

- `src/utils/api.ts`
- `src/views/dashboard/index.vue`
- `src/views/netdisk/logs.vue`
- `src/views/netdisk/risk.vue`

## 3. 核心实现说明

- 日志列表和导出支持 `start_date`、`end_date`，格式为 `YYYY-MM-DD`。
- CSV 导出使用 UTF-8 BOM，便于 Excel 打开中文。
- 看板新增 `point_sources`，按当天 `source + change_type` 聚合非 0 积分流水。
- 待追缴“追缴扣除”从用户当前可用积分扣除，部分扣除后继续保留 open 状态，扣清后变为 cleared。
- 待追缴“人工关闭”不扣分，直接将记录置为 cleared，并写入操作日志。

## 4. 已运行测试

| 测试命令 / 方式 | 结果 |
|---|---|
| `/private/tmp/vedo-backend-venv/bin/python -m py_compile controllers/admin.py` | 通过 |
| `PATH="$HOME/.local/bin:$PATH" npm run build` | 通过 |
| `GET /admin/netdisk/ops-dashboard` | 通过，返回 `point_sources` |
| `GET /admin/netdisk/audit-logs?start_date=2026-06-12&end_date=2026-06-12` | 通过 |
| `GET /admin/netdisk/audit-logs/export?start_date=2026-06-12&end_date=2026-06-12` | 通过，返回 CSV |
| `POST /admin/netdisk/risk-records/{id}/waive` | 通过，状态变为 cleared |
| 查询 `risk_waive` 操作日志 | 通过 |
| 浏览器打开 `/dashboard` | 通过，可见“今日积分来源分布” |
| 浏览器打开 `/logs` | 通过，可见日期控件和导出按钮 |
| 浏览器打开 `/risks` | 通过，可见“追缴扣除 / 人工关闭” |

## 5. 未覆盖测试项

- 未验证用户可用积分充足时的完整追缴扣除 UI 点击流程，只验证了后端处理能力和前端按钮展示。
- 日志导出未做大数据量性能测试，当前限制最多导出 5000 条。

## 6. 风险和建议

- 待追缴人工关闭会直接清除追缴状态，需要运营人工谨慎使用。
- 后续建议增加“仅查看 open / cleared 的快捷统计”和“追缴处理二次确认文案”。
