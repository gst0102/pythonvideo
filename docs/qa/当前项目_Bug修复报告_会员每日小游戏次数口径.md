# 当前项目 Bug 修复报告：会员每日小游戏次数口径

生成日期：2026-06-07

## 1. 修复目标

按 AI 测试官验收报告 v4 中的 P0 Bug 单 1 执行修复：

```text
会员每日小游戏次数默认值与阶段二 v2 文档不一致
```

开发文档要求：

```text
普通用户 / 月卡 / 季卡 / 年卡 = 20 / 100 / 200 / 300
```

本次只修复会员每日小游戏次数口径相关逻辑，不处理四方对账、D+2 自动兜底、二级分销等其他 P0 项。

## 2. 修改文件列表

| 文件 | 修改内容 |
|---|---|
| `D:\Desktop\vedo-project\myproject\services\game_task_service.py` | 将默认每日小游戏次数从 `10 / 100 / 150 / 200` 调整为 `20 / 100 / 200 / 300` |
| `D:\Desktop\vedo-project\myproject\services\config_service.py` | 将会员套餐默认次数从 `100 / 150 / 200` 调整为 `100 / 200 / 300` |
| `D:\Desktop\vedo-project\myproject\scripts\verify_vip_entitlements.py` | 将会员权益验证脚本断言从 `100 / 150 / 200` 调整为 `100 / 200 / 300` |

说明：当前工作区已有其他未提交改动，本报告仅记录本次针对 Bug 单 1 的改动。

## 3. 核心实现说明

### 3.1 游戏任务默认配置

`services/game_task_service.py` 中默认配置已改为：

```text
daily_game_task_limit_normal = 20
daily_game_task_limit_member_month = 100
daily_game_task_limit_member_quarter = 200
daily_game_task_limit_member_year = 300
```

### 3.2 会员套餐默认配置

`services/config_service.py` 中 `VIP_PACKAGE_DAILY_LIMITS` 已改为：

```text
month = 100
quarter = 200
year = 300
```

### 3.3 自测脚本断言

`scripts/verify_vip_entitlements.py` 中 `PERIOD_EXPECTATIONS` 已同步改为：

```text
month = 100
quarter = 200
year = 300
```

## 4. 已运行测试

| 编号 | 命令 | 结果 |
|---|---|---|
| T-001 | `python -m compileall controllers services schemas models scripts -q` | 通过 |
| T-002 | `python scripts\verify_vip_entitlements.py` | 通过 dry-run |
| T-003 | Python 常量断言：校验 `DEFAULT_TASK_CONFIG`、`VIP_PACKAGE_DAILY_LIMITS`、`PERIOD_EXPECTATIONS` | 通过 |
| T-004 | `rg -n "daily_game_task_limit_normal|daily_game_task_limit_member_|VIP_PACKAGE_DAILY_LIMITS|game_limit" ...` | 已确认目标值更新 |
| T-005 | `python scripts\verify_vip_entitlements.py --execute --period month` | 阻塞：本地库缺少 Stage 2 必需表 |
| T-006 | `python scripts\verify_vip_entitlements.py --execute --period quarter` | 阻塞：本地库缺少 Stage 2 必需表 |
| T-007 | `python scripts\verify_vip_entitlements.py --execute --period year` | 阻塞：本地库缺少 Stage 2 必需表 |

## 5. 验证结果

本地代码层面已确认：

```text
普通用户 / 月卡 / 季卡 / 年卡 = 20 / 100 / 200 / 300
```

真实事务脚本执行被本地数据库环境阻塞，错误为：

```text
Missing required tables for Stage 2 VIP entitlement verification:
daily_task_stats, points_ledger, user_accounts.
Run the Stage 2 Alembic migrations against the intended database first.
```

该阻塞说明当前本地验证数据库未完成 Stage 2 迁移，不代表本次代码常量修复失败。目标环境或完成迁移后的本地库仍需执行 `--execute` 三个会员周期的完整验证。

## 6. 未覆盖测试项

本次仅修复 Bug 单 1，以下 P0 项仍未覆盖或未闭环：

| 项目 | 状态 |
|---|---|
| 四方资产一致性 | 未修复 |
| D+2 自动兜底结算 | 未修复 |
| D+2 兜底幂等 | 未修复 |
| 二级分销收益 | 未修复 |
| 真实广告中断/游戏失败链路 | 未修复 |
| 历史配置隔离/迁移抽样 | 未修复 |

## 7. 影响范围

直接影响：

- 小游戏每日次数上限默认值。
- 会员套餐默认权益配置。
- 会员权益专项验证脚本期望值。

不直接影响：

- D+1/D+2 结算计算逻辑。
- 邀请/二级分销收益计算。
- 提现冻结和提现回调。
- 广告曝光/点击统计。

## 8. 需要 AI 测试官复核的事项

1. 在已完成 Stage 2 数据库迁移的目标环境中执行会员权益脚本：

```text
python scripts\verify_vip_entitlements.py --execute --period month
python scripts\verify_vip_entitlements.py --execute --period quarter
python scripts\verify_vip_entitlements.py --execute --period year
```

2. 复核接口返回、前端会员页展示、后台配置默认值是否均为：

```text
普通用户 / 月卡 / 季卡 / 年卡 = 20 / 100 / 200 / 300
```

3. 复核已有数据库中如果存在旧 `vip_settings` 或 `stage2_task_config` 配置，是否需要运营确认后做一次配置迁移或手动后台调整。

## 9. 修复结论

Bug 单 1 的代码默认值和验证脚本断言已修复。

当前整体项目仍不能判定通过，因为四方对账、D+2 自动兜底、二级分销收益等 P0 项尚未修复或闭环。本报告只支持进入“会员每日小游戏次数口径”这一项的复测。
