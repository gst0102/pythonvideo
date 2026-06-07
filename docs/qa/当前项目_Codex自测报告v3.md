# 当前项目 Codex 自测报告 v3

生成时间：2026-06-07

## 1. 本次自测目标

根据以下材料，对阶段二 v2 eCPM 结算改造进行开发侧自测，优先覆盖 P0 风险：

- `docs/yuexiang-stage2-docs/09-ecpm-settlement-rework.md`
- `docs/qa/当前项目_测试清单与验收标准v1.md`
- `AGENTS.md`

本轮只做自测与报告归档，未修改核心业务代码。

## 2. 自测环境与范围

- 后端仓库：`D:\Desktop\vedo-project\myproject`
- 小程序前端仓库：`D:\Desktop\vedo-project\video-ts`
- PC 后台仓库：`D:\Desktop\vedo-project\adminVideo`
- 生产后端：`https://api.lifelove.top`
- 生产 PC 后台：`https://admin.lifelove.top`
- 生产后端容器：`video-service-app`
- PC 后台发布版本：`adminVideo@bdc3162`
- 后端生产镜像：`pythonvideo-app:stage2-53f97b6`

## 3. 已执行测试命令

| 类型 | 命令 / 检查 | 结果 |
|---|---|---|
| 后端静态编译 | `python -m compileall controllers services schemas models scripts -q` | 通过 |
| D+1 结算专项 | `/app/.venv/bin/python scripts/verify_game_settlement_flow.py --execute` | 通过 |
| 积分提现专项 | `/app/.venv/bin/python scripts/verify_points_withdrawal_flow.py --execute` | 通过 |
| 签到专项 | `/app/.venv/bin/python scripts/verify_checkin_flow.py --execute` | 通过 |
| 小游戏广告专项 | `/app/.venv/bin/python scripts/verify_game_ad_flow.py --execute` | 通过 |
| 登录邀请专项 | `/app/.venv/bin/python scripts/verify_login_invite_flow.py --execute` | 通过 |
| 会员权益月卡 | `/app/.venv/bin/python scripts/verify_vip_entitlements.py --execute --period month` | 通过 |
| 会员权益季卡 | `/app/.venv/bin/python scripts/verify_vip_entitlements.py --execute --period quarter` | 通过，但发现口径差异 |
| 会员权益年卡 | `/app/.venv/bin/python scripts/verify_vip_entitlements.py --execute --period year` | 通过，但发现口径差异 |
| PC 后台构建 | `npm.cmd run build` | 通过 |
| 小程序类型检查 | `npm.cmd run type-check` | 通过 |
| 小程序微信构建 | `npm.cmd run build:mp-weixin` | 通过 |
| 线上健康检查 | `GET https://api.lifelove.top/health` | 200 |
| 线上结算查询 | `GET https://api.lifelove.top/admin/game-settlements/daily?settlement_date=2026-06-06` | 200 |
| 线上后台页面 | `GET https://admin.lifelove.top/finance/settlements` | 200 |

说明：生产容器内专项脚本均使用脚本内置 rollback transaction，不应持久化测试数据。

## 4. 已通过测试项

- TC-004 / TC-005：签到固定积分、重复签到拦截通过专项脚本验证。
- TC-007 / TC-010 / TC-011：小游戏广告完成后发放预估积分、同一广告事件和同一回合幂等通过专项脚本验证。
- TC-014 / TC-015 / TC-019 / TC-020：预估积分、D+1 结算、强制重算差额调整、结算摘要通过 `verify_game_settlement_flow.py` 验证。
- TC-021 / TC-035 / TC-036：提现锁定、失败退回、成功结清、流水类型通过 `verify_points_withdrawal_flow.py` 验证。
- TC-026 / TC-028 / TC-029：邀请绑定、防自邀、防重复绑定通过 `verify_login_invite_flow.py` 验证。
- TC-030 / TC-031：小游戏广告轮换、广告位耗尽、`ad_event_id` 幂等、同回合幂等通过 `verify_game_ad_flow.py` 验证。
- TC-037 / TC-038：会员支付后权益、`vip_gift` 流水、重复回调幂等由 `verify_vip_entitlements.py` 覆盖。
- TC-032 / TC-033：PC 后台结算页面已发布，线上页面 200，前端 chunk 包含 `/finance/settlements` 与“积分结算”路由。

## 5. 未覆盖测试项

- TC-001 / TC-002 / TC-003 / TC-022：未使用真实登录用户逐项核对首页、我的页、积分流水、后台结算四方数据。
- TC-006：连续签到、周日高亮、签到面板视觉表现未做人工 UI 验证。
- TC-008 / TC-009：小程序端真实激励广告中途退出、游戏失败场景未做真机验证。
- TC-012 / TC-024：每日游戏次数上限未用真实 20/100/200/300 次压测跑满。
- TC-017 / TC-018：D+2 自动兜底调度未做真实定时任务触发验证。
- TC-025：后台修改会员配置后“只影响未来数据”未做人工历史数据核对。
- TC-027：二级分销收益未在本轮自动化脚本中覆盖。
- TC-034：后台操作审计记录未覆盖。
- TC-039：所有前端收益文案未逐页人工巡检。
- TC-040：历史旧积分数据迁移后的抽样核对未覆盖。

## 6. 发现的问题

1. 会员每日小游戏次数默认值与新文档/测试清单不一致。
   - 文档和测试清单期望：普通 / 月卡 / 季卡 / 年卡 = `20 / 100 / 200 / 300`。
   - 当前代码和脚本显示：月卡 / 季卡 / 年卡 = `100 / 150 / 200`。
   - 涉及文件：`services/config_service.py`、`services/game_task_service.py`、`scripts/verify_vip_entitlements.py`。
   - 关联用例：TC-024。

2. 生产镜像内缺少 `scripts/verify_points_asset_consistency.py`。
   - 本地仓库有该脚本，但当前生产容器内不存在。
   - 影响：无法在生产容器内一键验证首页/我的页资产摘要、流水账户快照和账户余额的综合一致性。

3. 未执行生产 PUT/POST 结算写入测试。
   - 原因：避免用测试 eCPM、PV、有效点击、总收益污染真实生产运营数据。
   - 影响：PC 后台录入和触发按钮仍需测试官或运营在明确测试日期/测试账号下人工验证。

## 7. 建议修复项

1. 输出 Bug 单后修复会员每日次数口径。
   - 建议将默认值统一为 `20 / 100 / 200 / 300`，并同步更新验证脚本期望值。
   - 修复后回归 TC-012、TC-024、TC-037。

2. 下一版镜像补入 `verify_points_asset_consistency.py`。
   - 便于上线前在容器内直接跑四方资产一致性检查。

3. 为 D+2 兜底补独立自动化脚本。
   - 当前 D+1 和强制重算已覆盖，D+2 定时兜底仍需自动化闭环。

4. 为后台操作审计补测试点。
   - 当前 PC 后台结算页可操作，但审计日志未覆盖。

## 8. 需要人工确认部分

- 测试官需要使用真实后台账号登录 `https://admin.lifelove.top`，确认“财务管理 -> 积分结算”菜单可见。
- 测试官需要在可控测试日期录入 eCPM、PV、有效点击、总收益，并触发结算，核对 `points_ledger`、首页、我的页、后台结算结果一致。
- 测试官需要用微信开发者工具导入 `D:\Desktop\vedo-project\video-ts\dist\build\mp-weixin`，真机/模拟器验证签到面板、小游戏广告完成/中断、收益文案。
- 运营需确认会员次数默认值到底采用新文档 `20/100/200/300`，还是沿用当前代码 `20/100/150/200`。

## 9. 自测结论

结论：需要人工确认。

P0 中“重复发放、D+1 结算、提现口径、广告幂等、签到重复、邀请绑定、支付回调幂等”等核心风险已通过自动化或接口验证覆盖；但首页/我的页/积分流水/后台结算四方对账、D+2 自动兜底、真实小程序广告中断、会员次数口径仍未完全覆盖。

在测试官完整验收前，不建议直接给出“通过”结论。
