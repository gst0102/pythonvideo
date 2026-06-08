# 当前项目 Bug 修复报告：D+2 自动兜底结算

生成日期：2026-06-07

## 1. 修复目标

按 AI 测试官验收报告 v4 中的 P0 Bug 单 2 执行修复：

```text
D+2 自动兜底结算缺少真实调度级验收闭环
```

本次修复目标是补齐可复跑的专项验证脚本，让测试官可以验证：

1. 缺少手工 eCPM 时，系统按近 7 日历史 eCPM 均值兜底。
2. 同一结算日重复触发兜底，不重复生成结算流水。
3. 兜底后补录真实 eCPM 时，通过强制重算只生成差额调整。

## 2. 修改文件列表

| 文件 | 修改内容 |
|---|---|
| `D:\Desktop\vedo-project\myproject\scripts\verify_game_settlement_flow.py` | 补充 D+2 兜底、兜底幂等、兜底后补真实数据差额调整验证 |

本次未修改 D+1/D+2 结算服务主逻辑，原因是现有 `GameSettlementService` 已具备以下基础能力：

- `allow_fallback=True` 时可在无手工 eCPM 的情况下解析历史均值或默认 eCPM。
- 已结算批次在非 `force_recalculate` 下重复触发会直接返回详情，避免重复发放。
- `force_recalculate=True` 可在补录真实 eCPM 后重算并生成差额调整。
- 后台触发请求 `AdminGameSettlementTriggerRequest` 已包含 `force_recalculate` 字段。

## 3. 核心实现说明

新增脚本验证函数：

```text
_verify_d2_fallback_flow
```

验证流程：

1. 构造历史结算批次 eCPM 样本：`10.0 / 20.0 / 30.0`。
2. 构造 D+2 兜底结算日的普通用户和月卡 VIP 用户预估积分及广告事件。
3. 在未录入手工 eCPM 的情况下执行 `trigger_daily_settlement(..., allow_fallback=True)`。
4. 断言本次结算使用 `ecpm_source = rolling_average`，且 `ecpm_value = 20.0`。
5. 记录结算流水数量后重复触发兜底。
6. 断言重复触发不新增 `game_settlement / game_adjust_add / game_adjust_sub` 流水。
7. 后补真实 eCPM `30.0`，使用 `force_recalculate=True` 触发重算。
8. 断言用户可提现积分和用户结算明细只按差额调整到目标值。

## 4. 已运行测试

| 编号 | 命令 | 结果 |
|---|---|---|
| T-001 | `python -m compileall controllers services schemas models scripts -q` | 通过 |
| T-002 | `python scripts\verify_game_settlement_flow.py` | 通过 dry-run，输出已包含 D+2 fallback 验证范围 |
| T-003 | `rg -n "D\+2 fallback|fallback idempotency|rolling_average|manual truth after fallback|_verify_d2_fallback_flow|force_recalculate" ...` | 通过，确认新增验证点存在 |
| T-004 | `python scripts\verify_game_settlement_flow.py --execute` | 阻塞：本地库缺少 Stage 2 必需表 |

## 5. 本地阻塞说明

真实事务验证被当前本地数据库结构阻塞，错误为：

```text
Missing required tables for Stage 2 game settlement verification:
ad_event_records, game_rounds, game_settlement_batches,
game_user_settlements, points_ledger, user_accounts.
Run the Stage 2 Alembic migrations against the intended database first.
```

该阻塞说明本地数据库未完成 Stage 2 迁移，不代表脚本语法或验证逻辑失败。

## 6. 修复后必须回归

在已完成 Stage 2 迁移的目标环境中执行：

```text
python scripts\verify_game_settlement_flow.py --execute
```

期望输出包含：

```text
Game settlement verification passed
checks=first settlement, rerun adjustment, summary settled points, add/sub ledger entries, D+2 fallback, fallback idempotency, fallback adjustment
```

## 7. 未覆盖测试项

本次仅处理 Bug 单 2 的可复跑验证闭环，以下 P0 项仍未修复：

| 项目 | 状态 |
|---|---|
| 四方资产一致性 | 未修复 |
| 二级分销收益 | 未修复 |
| 真实广告中断/游戏失败链路 | 未修复 |
| 历史配置隔离/迁移抽样 | 未修复 |

## 8. 需要 AI 测试官复核的事项

1. 在目标数据库已迁移完成后执行 `python scripts\verify_game_settlement_flow.py --execute`。
2. 复核脚本是否真实覆盖 TC-017、TC-018、TC-019。
3. 复核后台触发接口传入 `force_recalculate=True` 时，兜底后补真实数据是否只生成一次差额调整。
4. 复核生产调度入口是否按 D+2 规则调用同一服务方法。

## 9. 修复结论

Bug 单 2 的专项验证脚本已补齐，后端静态编译和 dry-run 已通过。

由于本地数据库缺少 Stage 2 表，真实事务验证需在目标环境或完成迁移后的本地库中执行。本报告支持进入 D+2 自动兜底结算的测试官复测阶段，但整体项目仍不能判定通过，因为四方对账和二级分销收益等 P0 项仍未闭环。
