# 冻结积分奖励与资源消耗闭环_Codex自测报告

## 1. 本次修改目标

实现网盘资源上传和补链的冻结积分奖励口径：提交成功后先记录待验证冻结积分，不直接增加可用积分；资源解锁继续消耗可用积分。

## 2. 修改文件列表

- `services/netdisk_resource_service.py`
- `docs/new-docs/netdisk-resource-mutual-aid-mvp.md`
- `docs/qa/冻结积分奖励与资源消耗闭环_测试清单与验收标准.md`
- `docs/qa/冻结积分奖励与资源消耗闭环_Codex自测报告.md`

前端配套修改在 `video-ts` 仓库独立提交。

## 3. 核心实现说明

- 上传资源创建成功后写入一笔冻结积分流水：
  - `source=netdisk`
  - `availability=frozen`
  - `change_type=upload_reward_frozen`
  - `idempotency_key=netdisk_upload_frozen:{upload_id}`
- 补链创建成功后写入一笔冻结积分流水：
  - `source=netdisk`
  - `availability=frozen`
  - `change_type=repair_reward_frozen`
  - `idempotency_key=netdisk_repair_frozen:{repair_id}`
- 投诉不发放积分。
- 解锁资源仍通过 `consume_consumable_points` 扣 `consumable_points`，沿用资源表 `cost_points`。
- 本轮不做冻结积分释放，也不做失效确认扣回。

## 4. 已运行测试

| 测试命令 / 方式 | 结果 |
|---|---|
| `/private/tmp/vedo-backend-venv/bin/python -m py_compile services/netdisk_resource_service.py services/points_account_service.py controllers/netdisk.py schemas/netdisk.py` | 通过 |
| 本地接口：开发登录、上传资源、补链、投诉、解锁普通/精选/官方资源、重复解锁 | 通过 |
| 后端服务内幂等验证：同一上传/补链记录重复执行冻结奖励逻辑 | 通过 |

接口账务验证结果：

- 初始账户：`total=100`，`frozen=0`，`consumable=100`
- 上传后：`total=105`，`frozen=5`，`consumable=100`
- 补链后：`total=110`，`frozen=10`，`consumable=100`
- 投诉后：`total=110`，`frozen=10`，`consumable=100`
- 解锁普通、精选、官方资源后：`total=110`，`frozen=10`，`consumable=65`
- 最近网盘流水包含：
  - `upload_reward_frozen / frozen / +5`
  - `repair_reward_frozen / frozen / +5`
  - `resource_unlock / consumable / -5`
  - `resource_unlock / consumable / -10`
  - `resource_unlock / consumable / -20`

幂等验证结果：

- 同一上传记录重复执行冻结奖励逻辑后，上传奖励流水仍为 1 条。
- 同一补链记录重复执行冻结奖励逻辑后，补链奖励流水仍为 1 条。
- 账户 `frozen_points` 未重复增加。

## 5. 未覆盖测试项

- 未做并发压测，同一记录并发触发冻结奖励仍建议后续补数据库唯一索引或事务级回归。
- 未实现也未测试冻结积分释放为可用积分。
- 未实现也未测试失效确认后的冻结积分扣回或处罚。
- 未接后台审核页面，审核状态流转仍需后续联调。

## 6. 可能影响范围

- 网盘上传记录创建。
- 网盘补链/投诉记录创建。
- 用户积分账户与积分流水。
- 资源解锁扣可用积分流程。

## 7. 需要 AI 测试官复核的事项

- 冻结积分和可用积分前端展示是否足够清楚。
- 后续审核通过释放积分、失效确认扣回积分是否需要独立 P0 测试清单。
- 并发重复请求下是否需要为 `points_ledger.idempotency_key` 增加数据库唯一约束。
