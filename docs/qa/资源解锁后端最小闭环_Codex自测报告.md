# 资源解锁后端最小闭环 Codex 自测报告

## 1. 本次修改目标

实现网盘资源解锁后端最小闭环：真实扣减 `consumable_points`、写扣减流水、重复解锁不重复扣分，并在首次资源解锁成功后调用 `InviteRewardService.grant_first_resource_reward`。

## 2. 修改文件列表

- `services/points_account_service.py`
- `services/netdisk_resource_service.py`
- `controllers/netdisk.py`
- `schemas/netdisk.py`
- `main.py`
- `scripts/verify_netdisk_unlock_flow.py`
- `docs/qa/资源解锁后端最小闭环_Codex自测报告.md`

## 3. 核心实现说明

- 新增 `PointsAccountService.consume_consumable_points`：
  - 扣减 `consumable_points`。
  - 增加 `consumed_points`。
  - 写入 `points_ledger`，`source=netdisk`，`change_type=resource_unlock`，`points_delta` 为负数。
  - 使用 `idempotency_key` 防止同一资源重复扣分。
- 新增 `NetdiskResourceService.unlock_resource`：
  - 使用 MVP mock 资源目录。
  - 普通资源 `-5`，精选资源 `-10`，官方合集 `-20`。
  - 成功解锁后返回 mock 网盘链接、提取码、解压码。
  - 首次解锁成功后调用邀请首次资源奖励。
- 新增接口：
  - `POST /netdisk/resources/{resource_id}/unlock`
- 接口已挂载到 `main.py`。

## 4. 是否涉及高风险模块

涉及。该功能会扣减用户积分并触发邀请奖励，属于 P0 积分一致性链路。

## 5. 已运行测试

- `python -m py_compile services\points_account_service.py services\netdisk_resource_service.py controllers\netdisk.py schemas\netdisk.py scripts\verify_netdisk_unlock_flow.py main.py`
- `PYTHONUTF8=1 DATABASE_URL=postgresql+asyncpg://postgres:w12345@127.0.0.1:5432/agent_codex_test .\.venv\Scripts\python.exe scripts\verify_netdisk_unlock_flow.py --execute`
- `PYTHONUTF8=1 DATABASE_URL=postgresql+asyncpg://postgres:w12345@127.0.0.1:5432/agent_codex_test .\.venv\Scripts\python.exe scripts\verify_login_invite_flow.py --execute`

## 6. 测试结果

- 语法编译通过。
- 资源解锁执行态验证通过：
  - 首次解锁扣减 `consumable_points`。
  - 同一资源重复解锁不重复扣分。
  - 第二个资源可继续扣分。
  - 邀请首次资源奖励只发一次。
  - 余额不足时解锁失败。
  - 解锁流水数量符合预期。
- 邀请绑定/邀请奖励回归通过。

## 7. 未覆盖测试项

- 尚未接真实资源库表，当前资源目录仍为后端 mock catalog。
- 前端详情页尚未调用真实 `/netdisk/resources/{resource_id}/unlock`。
- 尚未实现资源解锁前的“已解锁状态查询”接口。
- 尚未覆盖并发重复点击同一资源解锁的数据库级行锁测试。
- 尚未实现退款/资源下架后的补偿逻辑。

## 8. 需要 AI 测试官复核的事项

- `total_points` 当前保持累计口径，本轮只扣 `consumable_points` 并增加 `consumed_points`，需确认产品口径。
- 解锁返回 mock 链接仅用于 MVP，接真实资源库前需复核内容合规与敏感链接权限。
- 后续前端接入时，需要确认未解锁状态下不展示链接/提取码。
