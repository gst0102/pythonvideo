# 邀请奖励最小闭环 Codex 自测报告

## 1. 本次修改目标

修复本地/测试库连接验证问题，跑通 `alembic upgrade head` 与 `verify_login_invite_flow.py --execute`，并进入“邀请奖励发放”最小闭环：基于 `invite_relations` 对注册/首次获取资源/首次充值三类事件写入幂等积分流水。

## 2. 修改文件列表

- `models/base.py`
- `services/invite_reward_service.py`
- `services/user_service.py`
- `services/__init__.py`
- `scripts/verify_login_invite_flow.py`
- `docs/qa/邀请奖励最小闭环_Codex自测报告.md`

## 3. 核心实现说明

- 修复数据库配置优先级：显式传入的 `DATABASE_URL` 优先于 `.env` 中的 `DB_HOST/DB_NAME`。
- 新增 `InviteRewardService`：
  - 邀请注册/绑定奖励：`+5` 积分。
  - 被邀请人首次获取资源奖励：`+10` 积分。
  - 被邀请人首次充值奖励：`+20` 积分。
- 三类奖励均写入 `points_ledger`，`source=invite`，`availability=consumable`。
- 三类奖励均使用确定性幂等键：
  - `invite:register:{relation_id}`
  - `invite:first_resource:{relation_id}`
  - `invite:first_recharge:{relation_id}`
- 邀请关系首次创建时自动发放注册奖励。
- 首次获取资源/首次充值先以服务方法提供，等待资源解锁与支付回调接入时调用。
- 扩展验证脚本，覆盖邀请绑定、绑定追踪、重复绑定不覆盖、自邀不绑定、三类奖励幂等。

## 4. 是否涉及高风险模块

涉及。该功能直接影响邀请奖励、积分余额、积分流水和重复发放风险，属于 P0 基础链路。

## 5. 已运行测试

- `python -m py_compile models\base.py services\invite_reward_service.py services\user_service.py services\__init__.py scripts\verify_login_invite_flow.py`
- `PYTHONUTF8=1 DATABASE_URL=postgresql+asyncpg://postgres:w12345@127.0.0.1:5432/agent_codex_test .\.venv\Scripts\python.exe -m alembic upgrade head`
- `PYTHONUTF8=1 DATABASE_URL=postgresql+asyncpg://postgres:w12345@127.0.0.1:5432/agent_codex_test .\.venv\Scripts\python.exe scripts\verify_login_invite_flow.py --execute`

## 6. 测试结果

- 语法编译通过。
- 新建本地测试库 `agent_codex_test` 后，完整 Alembic 迁移链跑到 head。
- 邀请绑定执行态验证通过。
- 邀请奖励幂等验证通过：
  - 注册奖励只发一次。
  - 首次获取资源奖励只发一次。
  - 首次充值奖励只发一次。
  - 无邀请关系用户不会获得邀请奖励。

## 7. 环境说明

- 原 `agent` 库存在历史半初始化状态：已有 `users` 和 `invite_relations`，但缺少 `alembic_version`、`user_accounts`、`points_ledger` 等 Stage 2 表。
- 为避免破坏原库，本轮使用独立测试库 `agent_codex_test` 验证完整迁移和执行态脚本。
- 本机 Postgres 可用连接参数为：`postgres:w12345@127.0.0.1:5432`。
- Windows 下运行 Alembic 需要设置 `PYTHONUTF8=1`，避免 `alembic.ini` 编码读取失败。

## 8. 未覆盖测试项

- 未把首次获取资源奖励接入真实资源解锁接口。
- 未把首次充值奖励接入真实支付成功回调。
- 未实现每日邀请奖励上限 `50` 分。
- 未实现异常设备/同微信环境风控。
- 未实现奖励撤销、退款后回滚、支付回调幂等联动。

## 9. 需要 AI 测试官复核的事项

- 奖励积分进入 `consumable_points` 是否符合最终产品规则。
- 资源解锁和支付回调接入时，是否严格调用同一套 `InviteRewardService`。
- 后续补每日邀请奖励上限时，需要复核并发场景下的上限一致性。
