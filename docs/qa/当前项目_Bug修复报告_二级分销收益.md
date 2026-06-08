# 当前项目 Bug 修复报告：二级分销收益

生成日期：2026-06-07

## 1. 修复目标

按 AI 测试官验收报告 v4 中的 P0 Bug 单 4 执行修复：

```text
二级分销收益缺少验证闭环
```

本次修复目标是补齐二级分销收益专项脚本的闭环验证，覆盖：

1. A 邀请 B、B 邀请 C 的二级关系。
2. C 购买 VIP 后，B 获得一级收益，A 获得二级收益。
3. 一级和二级收益均先进入冻结积分。
4. 重复支付回调不重复生成佣金记录和冻结流水。
5. 一级和二级收益解冻均具备幂等保护。

## 2. 修改文件列表

| 文件 | 修改内容 |
|---|---|
| `D:\Desktop\vedo-project\myproject\scripts\verify_invite_rebate_flow.py` | 补充二级收益释放、二级重复释放、二级解冻流水唯一、重复回调后记录数量不变的断言 |

本次未修改 `payment_service.py` 和 `commission_service.py` 主业务逻辑。现有服务已具备以下基础能力：

- 支付成功后根据 `parent_id` 生成一级收益。
- 支付成功后根据 `grand_parent_id` 生成二级收益。
- 佣金记录按 `order_id + level + user_id` 做幂等。
- 冻结积分按 `invite_rebate:{order_id}:{level}:{user_id}` 做幂等。
- 解冻积分按 `invite_rebate_unfreeze:{record.id}` 做幂等。

## 3. 核心实现说明

在 `verify_invite_rebate_flow.py` 中新增以下断言：

1. `level2 release created = True`。
2. `level2 release status = settled`。
3. 重复释放二级收益返回 `False`。
4. 二级收益释放后，二级邀请人的 `withdrawable_points = 50`。
5. 二级收益释放后，二级邀请人的 `frozen_points = 0`。
6. 二级 `invite_rebate_unfreeze` 流水数量为 `1`。
7. 重复支付回调后，当前订单佣金记录数量仍为 `2`。

## 4. 已运行测试

| 编号 | 命令 | 结果 |
|---|---|---|
| T-001 | `python -m compileall controllers services schemas models scripts -q` | 通过 |
| T-002 | `python scripts\verify_invite_rebate_flow.py` | 通过 dry-run，输出已包含 level2 unfreeze idempotency |
| T-003 | `rg -n "level2 release|level2 unfreeze|commission record count after duplicate|level2 unfreeze idempotency" scripts\verify_invite_rebate_flow.py` | 通过，确认新增断言存在 |
| T-004 | `python scripts\verify_invite_rebate_flow.py --execute` | 阻塞：本地库缺少 Stage 2 必需表 |

## 5. 本地阻塞说明

真实事务验证被当前本地数据库结构阻塞，错误为：

```text
Missing required tables for invite-rebate verification:
points_ledger, user_accounts.
Run the Stage 2 Alembic migrations against the intended database first.
```

该阻塞说明本地数据库未完成 Stage 2 迁移，不代表脚本语法或验证逻辑失败。

## 6. 修复后必须回归

在已完成 Stage 2 迁移的目标环境中执行：

```text
python scripts\verify_invite_rebate_flow.py --execute
```

期望输出包含：

```text
Invite rebate verification passed
checks=level1 50%, level2 5%, frozen points, duplicate callback idempotency, level1 unfreeze idempotency, level2 unfreeze idempotency
```

## 7. 未覆盖测试项

本次仅处理 Bug 单 4 的验证闭环，以下 P0 项仍未修复或未闭环：

| 项目 | 状态 |
|---|---|
| 四方资产一致性 | 未修复 |
| 真实广告中断/游戏失败链路 | 未修复 |
| 历史配置隔离/迁移抽样 | 未修复 |

## 8. 需要 AI 测试官复核的事项

1. 在目标数据库已迁移完成后执行 `python scripts\verify_invite_rebate_flow.py --execute`。
2. 复核 TC-027：二级分销收益是否正确到账、不漏发、不重复、不串级。
3. 复核重复支付回调后，佣金记录和冻结流水均不重复。
4. 复核一级和二级收益解冻后，流水、余额、冻结积分三者一致。

## 9. 修复结论

Bug 单 4 的专项验证脚本已补齐，后端静态编译和 dry-run 已通过。

由于本地数据库缺少 Stage 2 表，真实事务验证需在目标环境或完成迁移后的本地库中执行。本报告支持进入二级分销收益的测试官复测阶段，但整体项目仍不能判定通过，因为四方资产一致性、真实广告失败链路、历史配置隔离/迁移抽样等 P0 项仍未闭环。
