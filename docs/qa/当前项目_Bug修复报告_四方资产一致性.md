# 当前项目 Bug 修复报告：四方资产一致性

生成日期：2026-06-07

## 1. 修复目标

按 AI 测试官验收报告 v4 中的 P0 Bug 单 3 执行修复：

```text
四方资产一致性验收仍未形成目标环境闭环
```

本次修复目标是补齐四方核账专项脚本，使其覆盖：

1. 首页收益摘要。
2. 我的资产页积分钱包。
3. 积分流水和账户余额。
4. 后台结算详情。

## 2. 修改文件列表

| 文件 | 修改内容 |
|---|---|
| `D:\Desktop\vedo-project\myproject\scripts\verify_points_asset_consistency.py` | 补充首页摘要、后台结算详情、昨日已结算积分四方一致性断言 |

本次未修改首页、我的资产、后台结算或积分账户服务主逻辑，只补齐专项验证闭环。

## 3. 核心实现说明

脚本新增验证内容：

1. 构造受控的昨日结算批次 `GameSettlementBatch`。
2. 构造同一用户的昨日结算明细 `GameUserSettlement`。
3. 调用 `HomeOverviewService.get_overview` 获取首页摘要。
4. 调用 `MineAssetsService.get_assets` 获取我的资产页口径。
5. 调用 `PointsLedgerService.list_user_ledger` 获取流水账户口径。
6. 调用 `GameSettlementService.get_daily_detail` 获取后台结算详情。
7. 断言以下字段一致：

```text
首页 yesterday_settled_points = 120
我的资产 yesterday_settled_points = 120
后台结算用户 settled_points = 120
后台结算批次 total_settled_points = 120
账户余额 = 我的资产钱包 = 流水账户快照
```

## 4. 已运行测试

| 编号 | 命令 | 结果 |
|---|---|---|
| T-001 | `python -m compileall controllers services schemas models scripts -q` | 通过 |
| T-002 | `python scripts\verify_points_asset_consistency.py` | 通过 dry-run，输出已包含 home summary 和 admin settlement |
| T-003 | `rg -n "home yesterday settled|mine yesterday settled|admin settlement|HomeOverviewService|GameSettlementService|game_settlement" scripts\verify_points_asset_consistency.py` | 通过，确认新增断言存在 |
| T-004 | `python scripts\verify_points_asset_consistency.py --execute` | 阻塞：本地库缺少 Stage 2 必需表 |

## 5. 本地阻塞说明

真实事务验证被当前本地数据库结构阻塞，错误为：

```text
Missing required tables for asset consistency verification:
checkin_records, daily_task_stats, game_rounds,
game_settlement_batches, game_user_settlements,
points_ledger, user_accounts.
Run the Stage 2 Alembic migrations against the intended database first.
```

该阻塞说明本地数据库未完成 Stage 2 迁移，不代表脚本语法或验证逻辑失败。

## 6. 修复后必须回归

在已完成 Stage 2 迁移的目标环境中执行：

```text
python scripts\verify_points_asset_consistency.py --execute
```

期望输出包含：

```text
Points asset consistency verification passed
checks=checkin, game, invite frozen rebate, withdrawal lock/return, home summary, mine assets, ledger account, admin settlement
```

## 7. 未覆盖测试项

本次仅处理 Bug 单 3 的四方核账验证闭环，以下 P0 项仍需继续处理：

| 项目 | 状态 |
|---|---|
| 真实广告中断/游戏失败链路 | 未修复 |
| 历史配置隔离/迁移抽样 | 未修复 |

## 8. 需要 AI 测试官复核的事项

1. 在目标数据库已迁移完成后执行 `python scripts\verify_points_asset_consistency.py --execute`。
2. 复核 TC-001、TC-003、TC-022 是否已形成首页、我的资产、积分流水、后台结算四方一致性证据。
3. 复核真实目标环境中是否存在历史配置或旧数据导致的口径差异。

## 9. 修复结论

Bug 单 3 的专项验证脚本已补齐，后端静态编译和 dry-run 已通过。

由于本地数据库缺少 Stage 2 表，真实事务验证需在目标环境或完成迁移后的本地库中执行。本报告支持进入四方资产一致性的测试官复测阶段，但整体项目仍需继续处理真实广告失败链路和历史配置/迁移抽样等 P0 风险。
