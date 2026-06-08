# 当前项目 Codex 自测报告

## 1. 本次修改目标

根据 `docs/yuexiang-stage2-docs/` 与 `docs/qa/当前项目_测试清单与验收标准.md` 执行当前阶段二项目自测，优先覆盖 P0 风险项，并输出真实通过项、未覆盖项、发现的问题、建议修复项与需要人工确认部分。

本轮未修改核心业务代码，仅补了 1 处自测脚本兼容性问题，确保生产运行时 Python 3.10 可以执行现有 VIP 权益验证脚本。

## 2. 修改文件列表

- `d:\Desktop\vedo-project\myproject\scripts\verify_vip_entitlements.py`
- `d:\Desktop\vedo-project\myproject\docs\qa\当前项目_Codex自测报告.md`

## 3. 核心实现说明

- 使用已有专项脚本优先覆盖 P0：
  - `scripts/verify_game_ad_flow.py`
  - `scripts/verify_vip_entitlements.py`
- 在生产运行环境中执行回滚式验证，不留测试脏数据。
- 对前端执行编译验证，确认小游戏、我的页等阶段二接线后的基础构建可通过。
- 将 `verify_vip_entitlements.py` 中 `datetime.UTC` 调整为兼容 Python 3.10 的写法，仅影响测试脚本运行，不影响业务逻辑。

## 4. 已执行测试

### 4.1 后端静态校验

- `python -m py_compile controllers\game.py controllers\withdrawal.py controllers\vip.py controllers\points.py services\game_task_service.py services\game_ad_service.py services\withdrawal_service.py services\payment_service.py services\points_account_service.py services\points_ledger_service.py schemas\game.py schemas\points.py`
- `python -m py_compile scripts\verify_vip_entitlements.py scripts\verify_game_ad_flow.py`

### 4.2 后端专项脚本

- 本地 dry-run：
  - `python scripts\verify_vip_entitlements.py`
  - `python scripts\verify_game_ad_flow.py`
- 生产容器真实执行：
  - `docker exec video-service-app python scripts/verify_vip_entitlements.py --execute`
  - `docker exec video-service-app python scripts/verify_game_ad_flow.py --execute`

### 4.3 前端校验

- `npm.cmd run build:mp-weixin`
- `npm.cmd run type-check`

### 4.4 生产接口检查

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/game/tasks/status`
- `GET http://127.0.0.1:8000/admin/ad/game-bonus-config`

## 5. 已通过测试项

### 5.1 P0 已确认通过

- `TC-013` 石头剪刀布正常结算积分
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。
  - 已验证 `game_rounds`、积分发放、基础结算链路可执行。

- `TC-014` 同一 `round_id` 不可重复发积分
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。
  - 已验证同一局重复结算不会重复发奖。

- `TC-017` 游戏广告加成奖励与基础奖励一致性
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。
  - 已验证广告加倍基于已完成回合生效，且积分流水存在。

- `TC-018` 多广告 ID 轮换与限次生效
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。
  - 已验证单广告位超限后切换下一个广告位，全部超限后返回不可用提示。

- `TC-025` 会员开通后权益即时生效
  - 通过 `verify_vip_entitlements.py --execute` 覆盖。
  - 已验证会员状态生效、赠送积分到账、每日任务次数提升、提现门槛按会员口径生效。

- `TC-035` 会员支付成功回调不能重复开权益/返利
  - 本轮脚本覆盖了支付成功后权益与赠送积分只落一笔的主链验证。
  - 已确认 `vip_gift` 流水生成，幂等键为 `vip_gift:{order.id}`。
  - 但“重复回调请求两次”的完整重复调用回放，本轮未单独复现，见“未覆盖测试项”。

- `P0 广告幂等/防刷收益`
  - 已验证同一 `ad_event_id` 不重复发奖。
  - 已验证同一回合同一广告加倍不会重复到账。

- `P0 线上部署可用性`
  - `/health` 返回 `200`
  - `/game/tasks/status` 未登录返回 `401`
  - `/admin/ad/game-bonus-config` 返回 `200`
  - 已确认生产广告池配置存在 3 个真实广告位：
    - `adunit-e66ca7039925b740`
    - `adunit-7c61b0922792ddc9`
    - `adunit-a921c4e0383a451f`

### 5.2 非 P0/基础校验通过

- 前端 `build:mp-weixin` 编译通过。
- 后端相关控制器、服务、Schema、专项脚本 `py_compile` 通过。

## 6. 未覆盖测试项

以下项本轮没有被自动化或真实联调完整覆盖，不能判定为已通过：

- `TC-001` 新用户静默登录自动建档
- `TC-002` 邀请码随静默登录绑定上级
- `TC-003` 禁止自己邀请自己
- `TC-004` token 鉴权不信任前端 `user_id`
- `TC-007` 普通用户每日签到成功
- `TC-008` 同一天重复签到不重复发积分
- `TC-009` 会员签到加成生效
- `TC-011` 签到广告加成仅发放一次
- `TC-015` 普通用户超过每日 10 次后不可继续得分
- `TC-016` 不同会员等级任务次数上限正确
- `TC-019` 我的页面统一积分资产展示正确
- `TC-020` 每次积分变化都有对应流水
- `TC-021` 不满足门槛时不能提现
- `TC-022` 满足门槛时提现申请成功并冻结积分
- `TC-023` 提现驳回后积分退回
- `TC-026` 一级返利/二级分销冻结入账正确
- `TC-027` 用户只能绑定一次上级
- `TC-029` 免费用户复制资源前需完成互动/广告
- `TC-032` 前台不得出现高收益承诺文案
- `TC-034` 账户汇总、流水、页面展示三方一致
- `TC-036` 退款后奖励处理正确

说明：

- 本地数据库未迁移到完整阶段二表结构，导致本地 `--execute` 无法覆盖账务链路。
- 当前仓库内没有现成的登录/签到/提现/邀请/退款专项验证脚本，本轮未额外扩写业务测试脚本，以避免扩大修改范围。
- 真机微信静默登录、邀请码链路、影视资源权限链路需要小程序端与真实账号配合验证。

## 7. 发现的问题

### 7.1 已修复

- `verify_vip_entitlements.py` 原实现依赖 `datetime.UTC`，在生产运行时 Python 3.10 中会报错，导致 VIP 权益脚本无法执行。
- 本轮已修复为兼容写法，仅影响测试脚本，不影响业务逻辑。

### 7.2 当前仍存在的问题

- `npm.cmd run type-check` 失败。
  - 报错位置：`vue-tsc`
  - 报错摘要：`Search string not found: "/supportedTSExtensions = .*(?=;)/"`
  - 初步判断：当前 `vue-tsc` 与 `Node.js v22.18.0` / TypeScript 组合存在工具链兼容问题，不是本轮阶段二业务逻辑直接报错。

- 本地数据库缺少阶段二关键表，导致以下本地真实执行被阻断：
  - `daily_task_stats`
  - `points_ledger`
  - `user_accounts`
  - `ad_event_records`
  - `game_rounds`

## 8. 建议修复项

- 优先处理前端类型检查工具链兼容问题。
  - 建议固定一套已验证的 `Node LTS + vue-tsc + typescript` 组合。
  - 否则后续前端回归只能依赖构建通过，缺少类型层拦截。

- 为未覆盖的 P0 主链补专项验证脚本或 Postman/pytest 用例：
  - 静默登录 + 邀请绑定
  - 签到成功/重复签到/签到广告幂等
  - 提现申请/驳回退回
  - 邀请返利/二级分销/冻结积分
  - 汇总账户、流水、页面展示一致性

- 在本地或 CI 提供一套已迁移的阶段二测试数据库，避免关键账务验证只能依赖生产容器回滚式执行。

## 9. 需要人工确认部分

- 微信静默登录、邀请码绑定、自邀拦截与重复绑定拦截，需要真实小程序登录链路验证。
- 前端关键页面文案合规，需要按清单人工巡检：
  - 首页
  - 任务页
  - 会员页
  - 邀请页
- 我的页面资产展示、积分明细展示、提现弹窗交互，需要真机页面核对。
- 影视资源权益控制，需要真实普通用户/会员用户账户做前台行为验证。
- 支付回调重复回放、退款逆向处理、邀请返利冻结与解冻流程，需要联调数据或后台管理入口配合验证。

## 10. 是否涉及高风险模块

涉及。已触达或验证到的高风险模块包括：

- 小游戏结算
- 广告加倍
- 广告轮换与限次
- 会员开通后权益落账
- 积分流水
- 提现门槛摘要

未完全覆盖但仍属于高风险的模块包括：

- 微信登录与邀请绑定
- 签到
- 提现申请与退回
- 一级返利 / 二级分销
- 退款逆向
- 页面展示与账务一致性

## 11. 测试结果结论

本轮不能给出“全量通过”结论，但可以确认以下事实：

- 小游戏结算、广告加倍、广告轮换与幂等这条阶段二核心 P0 链路已在生产运行环境中真实通过。
- 会员开通后赠送积分、任务次数提升、提现门槛切换这条核心权益链路已在生产运行环境中真实通过。
- 前端微信小程序构建可通过，当前阻塞主要在 `vue-tsc` 工具链兼容，而不是已验证业务链路直接失败。

当前最需要 AI 测试官或人工继续复核的，是登录/签到/提现/邀请/退款/页面一致性这几条仍未覆盖的 P0 主链。
