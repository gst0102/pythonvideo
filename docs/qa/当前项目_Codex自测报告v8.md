# 当前项目 Codex 自测报告 v8

生成时间：2026-06-07

## 1. 本次自测目标

基于以下材料重新执行 Codex 自测，并优先验证 P0 项：

1. `docs/yuexiang-stage2-docs/09-ecpm-settlement-rework.md`
2. `docs/qa/当前项目_测试清单与验收标准v1.md`
3. `AGENTS.md`

本轮不再只重复归档“不通过”结论，而是按 AI 测试官验收报告中已给出的 P0 Bug 单执行修复后自测。修复范围仅覆盖 Bug 单列出的阻断点，不主动扩展到无关核心业务代码。

## 2. 验收结论

结论：需要人工确认。

原因：

1. 会员每日小游戏次数口径已按文档修正为 `20 / 100 / 200 / 300`，并完成静态核验。
2. 四方资产一致性、D+2 自动兜底、二级分销收益 3 个 P0 项已补充专项验证脚本断言，dry-run 通过。
3. 后端静态编译、PC 后台构建、小程序类型检查和微信构建均通过。
4. 本地 `--execute` 真实执行模式被数据库缺少 Stage 2 表结构阻断，未能在真实库完成 P0 数据落库级验收。
5. 真实广告失败链路、历史配置隔离/迁移抽样仍需要目标环境或人工联调确认。

因此，本轮相比 v7 已完成 P0 Bug 单对应修复与脚本补强，但在目标数据库迁移并执行真实脚本前，不建议直接进入上线确认。

## 3. 本轮修复范围

### 3.1 会员每日小游戏次数口径

修复内容：

- 普通用户每日小游戏次数默认值修正为 `20`。
- 月卡、季卡、年卡每日小游戏次数修正为 `100 / 200 / 300`。
- 会员权益验证脚本同步更新断言。

涉及文件：

- `services/game_task_service.py`
- `services/config_service.py`
- `scripts/verify_vip_entitlements.py`

### 3.2 D+2 自动兜底结算

修复内容：

- 在 `scripts/verify_game_settlement_flow.py` 中补充 D+2 兜底验证。
- 覆盖近 3 天滚动 eCPM 均值兜底。
- 覆盖重复执行不重复生成积分流水。
- 覆盖后续人工 eCPM 回填后强制重算产生差额调整。

涉及文件：

- `scripts/verify_game_settlement_flow.py`
- `docs/qa/当前项目_Bug修复报告_D+2自动兜底结算.md`

### 3.3 二级分销收益

修复内容：

- 在 `scripts/verify_invite_rebate_flow.py` 中补充二级收益释放验证。
- 覆盖二级收益从 frozen 到 withdrawable 的释放。
- 覆盖重复释放幂等。
- 覆盖重复支付回调不重复生成分销收益记录。

涉及文件：

- `scripts/verify_invite_rebate_flow.py`
- `docs/qa/当前项目_Bug修复报告_二级分销收益.md`

### 3.4 四方资产一致性

修复内容：

- 在 `scripts/verify_points_asset_consistency.py` 中补充四方资产一致性断言。
- 覆盖用户账户、积分流水、首页汇总、我的资产、后台结算明细。
- 覆盖签到、小游戏、邀请冻结、提现锁定、提现退回后的账户一致性。

涉及文件：

- `scripts/verify_points_asset_consistency.py`
- `docs/qa/当前项目_Bug修复报告_四方资产一致性.md`

## 4. 已执行测试命令

| 编号 | 命令 | 结果 | 说明 |
|---|---|---|---|
| T-001 | `python -m compileall controllers services schemas models scripts -q` | 通过 | 后端 Python 静态编译通过 |
| T-002 | `python scripts\verify_vip_entitlements.py` | 通过 | dry-run 通过，覆盖会员权益默认值 |
| T-003 | `python scripts\verify_game_settlement_flow.py` | 通过 | dry-run 通过，覆盖结算、重算、D+2 兜底 |
| T-004 | `python scripts\verify_invite_rebate_flow.py` | 通过 | dry-run 通过，覆盖一级、二级、幂等释放 |
| T-005 | `python scripts\verify_points_asset_consistency.py` | 通过 | dry-run 通过，覆盖资产一致性断言 |
| T-006 | `npm.cmd run type-check` | 通过 | 小程序 TypeScript 检查通过 |
| T-007 | `npm.cmd run build` | 通过 | PC 后台生产构建通过 |
| T-008 | `npm.cmd run build:mp-weixin` | 通过 | 小程序微信构建通过 |
| T-009 | `python scripts\verify_vip_entitlements.py --execute` | 阻断 | 本地数据库缺少 `daily_task_stats`、`points_ledger`、`user_accounts` |
| T-010 | `python scripts\verify_game_settlement_flow.py --execute` | 阻断 | 本地数据库缺少 `ad_event_records`、`game_rounds`、`game_settlement_batches`、`game_user_settlements`、`points_ledger`、`user_accounts` |
| T-011 | `python scripts\verify_invite_rebate_flow.py --execute` | 阻断 | 本地数据库缺少 `points_ledger`、`user_accounts` |
| T-012 | `python scripts\verify_points_asset_consistency.py --execute` | 阻断 | 本地数据库缺少 `checkin_records`、`daily_task_stats`、`game_rounds`、`game_settlement_batches`、`game_user_settlements`、`points_ledger`、`user_accounts` |

## 5. 已通过测试项

| 编号 | 模块 | 测试项 | 优先级 | 自测结果 |
|---|---|---|---|---|
| P0-01 | 会员权益 | 普通用户每日小游戏次数为 20 | P0 | 通过，代码与脚本断言已对齐 |
| P0-02 | 会员权益 | 月卡每日小游戏次数为 100 | P0 | 通过，代码与脚本断言已对齐 |
| P0-03 | 会员权益 | 季卡每日小游戏次数为 200 | P0 | 通过，代码与脚本断言已对齐 |
| P0-04 | 会员权益 | 年卡每日小游戏次数为 300 | P0 | 通过，代码与脚本断言已对齐 |
| P0-05 | 小游戏结算 | 首次结算生成用户收益与流水 | P0 | dry-run 通过 |
| P0-06 | 小游戏结算 | 重复结算不重复发放积分 | P0 | dry-run 通过 |
| P0-07 | 小游戏结算 | eCPM 重算产生增量/扣减调整流水 | P0 | dry-run 通过 |
| P0-08 | D+2 兜底 | D+2 缺少人工 eCPM 时使用滚动均值兜底 | P0 | dry-run 通过，真实执行待目标库 |
| P0-09 | D+2 兜底 | D+2 兜底重复执行保持幂等 | P0 | dry-run 通过，真实执行待目标库 |
| P0-10 | D+2 兜底 | 人工 eCPM 回填后可强制重算差额 | P0 | dry-run 通过，真实执行待目标库 |
| P0-11 | 邀请分销 | 一级收益比例与冻结入账 | P0 | dry-run 通过 |
| P0-12 | 邀请分销 | 二级收益比例与冻结入账 | P0 | dry-run 通过 |
| P0-13 | 邀请分销 | 一级收益释放幂等 | P0 | dry-run 通过 |
| P0-14 | 邀请分销 | 二级收益释放幂等 | P0 | dry-run 通过 |
| P0-15 | 资产一致性 | 用户账户余额与积分流水一致 | P0 | dry-run 通过 |
| P0-16 | 资产一致性 | 首页收益汇总与结算数据一致 | P0 | dry-run 通过 |
| P0-17 | 资产一致性 | 我的资产与账户、结算数据一致 | P0 | dry-run 通过 |
| P0-18 | 资产一致性 | 后台结算明细与用户结算表一致 | P0 | dry-run 通过 |
| P1-01 | PC 后台 | 生产构建 | P1 | 通过 |
| P1-02 | 小程序 | TypeScript 类型检查 | P1 | 通过 |
| P1-03 | 小程序 | 微信构建 | P1 | 通过 |

## 6. 未覆盖测试项

| 编号 | 模块 | 未覆盖内容 | 原因 | 建议补测方式 |
|---|---|---|---|---|
| U-001 | P0 真实落库 | 4 个专项脚本的 `--execute` 真实数据库执行 | 本地数据库未应用 Stage 2 迁移，缺少必要表 | 在测试库/预发库执行 Alembic 迁移后重跑 `--execute` |
| U-002 | 广告链路 | 真实激励广告失败、取消、无回调、重复回调链路 | 需要微信/广告 SDK 或可控 mock 环境 | 使用小程序开发者工具、广告 mock 或预发环境联调 |
| U-003 | 历史配置隔离 | 老用户、旧配置、历史 VIP 套餐迁移抽样 | 本地缺少真实历史数据 | 在脱敏测试库抽样历史用户验证 |
| U-004 | 四方对账 | 大批量用户、多日结算、提现交叉下的全量对账 | 当前只完成脚本级样例覆盖 | 在目标库用多用户、多日期、多提现状态数据压测 |
| U-005 | 支付/退款 | 真实支付成功、失败、退款后的奖励与分销回滚 | 本轮 Bug 单未覆盖退款闭环 | 在支付沙箱或预发支付环境补测 |

## 7. 发现的问题

### 7.1 本地数据库未完成 Stage 2 迁移

执行 `--execute` 真实模式时，4 个专项验证脚本均被缺表检查拦截。

影响：

- 无法在当前本地库完成真实落库级 P0 验收。
- dry-run 只能证明脚本检查项、代码路径与断言设计已就绪，不能替代目标库验收。

### 7.2 真实广告失败链路仍缺少自动化证据

当前本轮主要覆盖结算、会员权益、分销收益和资产一致性。真实广告失败、取消、异常回调仍需要小程序真实环境或 mock 环境验证。

### 7.3 历史配置隔离/迁移抽样仍需人工确认

会员默认次数口径已修正，但历史配置、已有用户、已有 VIP 订单是否需要迁移或兼容策略，需要结合线上数据确认。

## 8. 建议修复项

1. 在测试库或预发库执行 Stage 2 Alembic 迁移，确保 `user_accounts`、`points_ledger`、`game_rounds`、`ad_event_records`、`game_settlement_batches`、`game_user_settlements`、`daily_task_stats`、`checkin_records` 等表存在。
2. 迁移完成后，按顺序执行 4 个专项脚本的 `--execute` 模式：
   - `python scripts\verify_vip_entitlements.py --execute`
   - `python scripts\verify_game_settlement_flow.py --execute`
   - `python scripts\verify_invite_rebate_flow.py --execute`
   - `python scripts\verify_points_asset_consistency.py --execute`
3. 补充广告失败链路专项自动化或半自动化脚本，覆盖广告取消、失败、无回调、重复回调、前端刷新重入。
4. 对历史 VIP 配置和老用户权益做抽样检查，确认是否需要一次性数据修正脚本。
5. 在目标库通过 `--execute` 后，再交给 AI 测试官做复测与回归报告，不建议跳过复测直接上线。

## 9. 需要人工确认部分

1. 是否允许先在预发库执行 Stage 2 迁移并跑 4 个 `--execute` 专项验证脚本。
2. 历史用户会员每日小游戏次数是否需要追溯修正，还是仅对新配置生效。
3. 广告失败链路是否已有可控 mock 环境；如果没有，需要人工在微信开发者工具或真机环境补测。
4. D+2 兜底使用近 3 天滚动 eCPM 均值是否符合最终业务口径。
5. 四方资产一致性是否需要扩大到全量历史数据对账。

## 10. 本轮输出物

Bug 修复报告：

- `docs/qa/当前项目_Bug修复报告_会员每日小游戏次数口径.md`
- `docs/qa/当前项目_Bug修复报告_D+2自动兜底结算.md`
- `docs/qa/当前项目_Bug修复报告_二级分销收益.md`
- `docs/qa/当前项目_Bug修复报告_四方资产一致性.md`

本自测报告：

- `docs/qa/当前项目_Codex自测报告v8.md`

## 11. Codex 自测结论

本轮已按 AI 测试官 Bug 单完成会员次数口径修正，并补齐 D+2 自动兜底、二级分销收益、四方资产一致性的专项验证脚本。静态编译、前端构建、小程序类型检查、小程序微信构建、4 个专项脚本 dry-run 均通过。

当前剩余阻断不是“完全未修”，而是本地数据库缺少 Stage 2 表结构，导致真实 `--execute` 落库验收无法执行。建议下一步在迁移后的测试库/预发库跑完 4 个专项脚本真实模式，再由 AI 测试官输出复测与回归报告。
