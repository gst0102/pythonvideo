# 网盘审核释放与失效处罚_Codex自测报告

## 1. 本次修改目标

补齐网盘资源贡献奖励的审核闭环：

- 上传/补链审核通过后，将冻结积分释放为可用积分。
- 上传/补链拒绝或确认失效后，扣回冻结奖励；已释放奖励则处罚可用积分。
- 投诉超过 3 条后先隐藏资源。
- 提供后台管理接口：上传、补链/投诉列表，以及通过、拒绝、确认失效操作。
- 补充 `points_ledger.idempotency_key` 唯一约束兜底迁移。

## 2. 修改文件列表

- `controllers/admin.py`
- `services/netdisk_resource_service.py`
- `services/points_account_service.py`
- `schemas/netdisk.py`
- `migrations/versions/012_ensure_points_ledger_idempotency_unique.py`
- `docs/new-docs/netdisk-resource-mutual-aid-mvp.md`
- `docs/qa/网盘审核释放与失效处罚_测试清单与验收标准.md`
- `docs/qa/网盘审核释放与失效处罚_Codex自测报告.md`

## 3. 核心实现说明

- 新增积分账户方法：
  - `move_frozen_to_consumable`：冻结积分释放为可用积分，流水 `points_delta=0`。
  - `deduct_frozen_points`：扣回冻结奖励，扣减总积分和冻结积分。
- 新增网盘审核服务：
  - 上传：列表、通过、拒绝、确认失效。
  - 补链/投诉：列表、通过、拒绝、确认失效。
- 审核幂等键：
  - `netdisk_upload_release:{upload_id}`
  - `netdisk_repair_release:{repair_id}`
  - `netdisk_upload_clawback:{upload_id}:{reason}`
  - `netdisk_upload_penalty:{upload_id}:{reason}`
  - `netdisk_repair_clawback:{repair_id}:{reason}`
  - `netdisk_repair_penalty:{repair_id}:{reason}`
- 投诉隐藏规则：
  - 同一资源达到 3 条未驳回投诉后，设置 `is_active=false`。
  - 隐藏不等于处罚，后台确认失效后才处罚对应上传/补链奖励。

## 4. 已运行测试

| 测试命令 / 方式 | 结果 |
|---|---|
| `/private/tmp/vedo-backend-venv/bin/python -m py_compile services/points_account_service.py services/netdisk_resource_service.py controllers/admin.py schemas/netdisk.py` | 通过 |
| 本地接口：上传通过释放、重复通过、确认失效处罚、重复确认失效 | 通过 |
| 本地接口：上传拒绝扣回冻结奖励 | 通过 |
| 本地接口：补链通过释放、确认失效处罚、补链拒绝扣回 | 通过 |
| 本地接口：3 条投诉不奖励并自动隐藏资源 | 通过 |
| 后台列表接口：上传列表、补链/投诉列表 | 通过 |
| 并发测试：5 个并发上传通过请求 | 通过，释放流水只有 1 条 |

关键账务结果：

- 上传创建：`total +5`，`frozen +5`，`consumable +0`
- 上传通过：`frozen -5`，`consumable +5`
- 上传确认失效：`consumable -5`
- 上传拒绝：`total -5`，`frozen -5`
- 补链通过：`frozen -5`，`consumable +5`
- 补链确认失效：`consumable -5`
- 补链拒绝：`total -5`，`frozen -5`
- 投诉 3 次：积分不变，资源从列表隐藏
- 并发审核：5 次请求成功，`upload_reward_release` 只有 1 条

## 5. 未覆盖测试项

- 未接 PC 后台页面，只完成后台接口。
- 未做跨进程高并发压测，只做本地 5 并发请求验证。
- 可用积分不足时，处罚仅扣当前可扣部分；剩余追缴/风控记录未实现。
- 未实现资源恢复上架接口。

## 6. 可能影响范围

- 积分账户汇总与积分流水。
- 网盘上传、补链、投诉状态。
- 网盘资源列表可见性。
- 后台管理接口。

## 7. 需要 AI 测试官复核的事项

- 处罚可用积分不足时是否需要增加“待追缴积分/风控状态”。
- 自动隐藏阈值 3 是否需要后台配置化。
- PC 后台页面接入后，需要重新做人工操作验收。
