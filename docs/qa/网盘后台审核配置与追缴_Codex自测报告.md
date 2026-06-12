# 网盘后台审核配置与追缴_Codex自测报告

## 1. 本次修改目标

- PC 后台支持网盘上传、补链、投诉审核入口。
- 后端支持待追缴/风控记录。
- 支持资源恢复上架和误投诉撤销。
- 将上传奖励、补链奖励、投诉隐藏阈值、失效处罚倍数放入后台配置。

## 2. 修改文件列表

后端：

- `controllers/admin.py`
- `models/netdisk_risk_record.py`
- `models/__init__.py`
- `schemas/netdisk.py`
- `services/config_service.py`
- `services/netdisk_resource_service.py`
- `migrations/versions/013_netdisk_risk_records_and_config.py`

PC 后台：

- `adminVideo/src/views/netdisk/review.vue`
- `adminVideo/src/router/index.ts`
- `adminVideo/src/layout/index.vue`
- `adminVideo/src/utils/api.ts`

## 3. 核心实现说明

- 新增 `netdisk_audit_config`：
  - `upload_reward_points`
  - `repair_reward_points`
  - `report_hide_threshold`
  - `invalid_penalty_multiplier`
  - `auto_hide_on_report`
- 新增 `netdisk_risk_records` 表记录可用积分不足时的待追缴积分。
- 失效处罚按 `奖励积分 * 处罚倍数` 计算。
- 用户可用积分不足时，先扣当前可扣积分，剩余写入待追缴记录。
- 驳回投诉后，如果未驳回投诉数低于阈值，则自动恢复资源可见。
- 后台新增资源恢复接口。
- PC 后台新增“网盘审核”页面，包含上传审核、补链/投诉、隐藏资源、待追缴、规则配置。

## 4. 已运行测试

| 测试命令 / 方式 | 结果 |
|---|---|
| `/private/tmp/vedo-backend-venv/bin/python -m py_compile services/netdisk_resource_service.py services/config_service.py controllers/admin.py models/netdisk_risk_record.py migrations/versions/013_netdisk_risk_records_and_config.py` | 通过 |
| `PATH="$HOME/.local/bin:$PATH" npm run build`（adminVideo） | 通过 |
| 本地接口：配置上传奖励 6、补链奖励 7、投诉阈值 2、处罚倍数 2 | 通过 |
| 本地接口：可用积分不足时确认失效，生成待追缴记录 | 通过 |
| 本地接口：投诉达到阈值自动隐藏资源 | 通过 |
| 本地接口：驳回误投诉后资源恢复 | 通过 |
| 本地接口：手动恢复资源上架 | 通过 |

关键验证结果：

- 上传奖励按配置进入冻结积分：`+6`
- 审核通过释放为可用积分：`+6`
- 2 倍处罚应扣 `12` 分，用户仅剩 `1` 可用积分时：
  - 可用积分扣 `1`
  - 待追缴记录 `points_due=11`
  - `points_collected=1`
- 投诉阈值为 `2` 时，两条投诉后资源隐藏。
- 驳回其中一条误投诉后，未驳回投诉数低于阈值，资源恢复可见。
- 手动恢复上架接口可恢复隐藏资源。

## 5. 未覆盖测试项

- PC 后台页面仅完成构建检查，未用浏览器逐项点击验收。
- 待追缴记录目前只记录，不自动从用户后续收入里追扣。
- 暂未提供待追缴记录人工关闭/减免接口。
- 配置修改未做权限校验，本项目当前后台接口整体仍是本地管理口径。

## 6. 可能影响范围

- 网盘上传奖励、补链奖励。
- 资源投诉隐藏和恢复。
- 积分处罚、可用积分扣减、待追缴记录。
- PC 后台菜单和构建产物。

## 7. 需要 AI 测试官复核的事项

- 待追缴记录是否需要进入用户详情页。
- 处罚倍数是否按资源等级区分。
- 后续是否需要“自动追扣后续可用积分”的定时任务。
