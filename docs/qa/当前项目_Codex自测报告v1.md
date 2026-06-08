# 当前项目 Codex 自测报告 v1

## 1. 本次修改目标

根据 [当前项目_验收报告.md](d:/Desktop/vedo-project/myproject/docs/qa/当前项目_验收报告.md) 的“不通过”结论，只围绕以下 3 类问题做收口：

1. 让阶段二关键 P0 验证脚本在可用验收环境中真正可执行。
2. 补齐登录/邀请、签到、积分提现这些此前缺少可复核证据的最小专项脚本。
3. 明确前端真实工程路径与构建证据，避免“命令写了但无法复核”的问题。

本轮没有扩大到无关业务重构，只修了 1 个真实默认配置问题和 1 个既有自测脚本兼容问题，并新增最小必要的验收脚本。

## 2. 修改文件列表

- [services/config_service.py](d:/Desktop/vedo-project/myproject/services/config_service.py)
- [scripts/verify_vip_entitlements.py](d:/Desktop/vedo-project/myproject/scripts/verify_vip_entitlements.py)
- [scripts/verify_login_invite_flow.py](d:/Desktop/vedo-project/myproject/scripts/verify_login_invite_flow.py)
- [scripts/verify_checkin_flow.py](d:/Desktop/vedo-project/myproject/scripts/verify_checkin_flow.py)
- [scripts/verify_points_withdrawal_flow.py](d:/Desktop/vedo-project/myproject/scripts/verify_points_withdrawal_flow.py)
- [当前项目_Codex自测报告v1.md](d:/Desktop/vedo-project/myproject/docs/qa/当前项目_Codex自测报告v1.md)

## 3. 核心实现说明

### 3.1 验收脚本补齐

新增 3 个专项脚本：

- `verify_login_invite_flow.py`
  - 覆盖新用户自动建档
  - 首次邀请码绑定
  - 不可重复改绑
  - 自己邀请码回流不自绑
  - token 仅基于 `openid`

- `verify_checkin_flow.py`
  - 覆盖普通用户签到
  - 重复签到幂等
  - 会员签到积分差异
  - `checkin_records`、`daily_task_stats`、`points_ledger` 一致性

- `verify_points_withdrawal_flow.py`
  - 覆盖首提/普通/会员门槛摘要
  - 门槛不足拦截
  - 可提现积分不足拦截
  - 提现申请锁定积分
  - 提现失败/驳回退回积分
  - 提现成功结转 `withdrawn_points`

### 3.2 既有脚本补强

- `verify_vip_entitlements.py`
  - 修复 Python 3.10 不支持 `datetime.UTC` 的兼容问题
  - 增加“同一支付成功回调重复执行一次”的幂等验证
  - 断言 `vip_gift` 流水只生成 1 条

### 3.3 业务修正

- 修正 `withdrawal_config` 默认提现门槛：
  - `withdraw_min_first = 1`
  - `withdraw_min_normal = 5`
  - `withdraw_min_member = 1`

这一步是为了对齐阶段二文档和提现验收规则，避免默认配置下普通用户后续提现门槛错误退化到 `0.10 元`。

## 4. 已执行测试

### 4.1 后端静态校验

- `python -m py_compile services\config_service.py scripts\verify_vip_entitlements.py scripts\verify_login_invite_flow.py scripts\verify_checkin_flow.py scripts\verify_points_withdrawal_flow.py`
- `python -m py_compile controllers\game.py controllers\withdrawal.py controllers\vip.py controllers\points.py services\game_task_service.py services\game_ad_service.py services\withdrawal_service.py services\payment_service.py services\points_account_service.py services\points_ledger_service.py schemas\game.py schemas\points.py`

### 4.2 本地 dry-run

- `python scripts\verify_login_invite_flow.py`
- `python scripts\verify_checkin_flow.py`
- `python scripts\verify_points_withdrawal_flow.py`
- `python scripts\verify_vip_entitlements.py`
- `python scripts\verify_game_ad_flow.py`

### 4.3 生产容器回滚式真实执行

执行环境：
- 服务器：`81.70.84.35`
- 分支：`feature/yuexiang-stage2-mvp`
- 当前提交：`0fa4f8e`
- 容器：`video-service-app`

真实执行通过：
- `docker exec video-service-app python scripts/verify_login_invite_flow.py --execute`
- `docker exec video-service-app python scripts/verify_checkin_flow.py --execute`
- `docker exec video-service-app python scripts/verify_points_withdrawal_flow.py --execute`
- `docker exec video-service-app python scripts/verify_vip_entitlements.py --execute`
- `docker exec video-service-app python scripts/verify_game_ad_flow.py --execute`

### 4.4 前端真实路径验证

前端工程真实路径：
- `d:\Desktop\vedo-project\video-ts`

执行命令：
- `npm.cmd run build:mp-weixin`
- `npm.cmd run type-check`

## 5. 已通过测试项

### 5.1 P0 已通过

- `TC-001` 新用户静默登录自动建档
  - 通过 `verify_login_invite_flow.py --execute` 覆盖到服务层建档与 `user_accounts` 初始化。

- `TC-002` 邀请码随登录绑定上级
  - 通过 `verify_login_invite_flow.py --execute` 覆盖 direct / indirect 关系绑定。

- `TC-003` 禁止自己邀请自己
  - 通过 `verify_login_invite_flow.py --execute` 覆盖“已有用户携带自己邀请码再次登录不自绑”。

- `TC-007` 普通用户每日签到成功
  - 通过 `verify_checkin_flow.py --execute` 覆盖。

- `TC-008` 同一天重复签到不重复发积分
  - 通过 `verify_checkin_flow.py --execute` 覆盖。

- `TC-009` 会员签到加成生效
  - 通过 `verify_checkin_flow.py --execute` 覆盖。

- `TC-013` 石头剪刀布正常结算积分
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。

- `TC-014` 同一 `round_id` 不可重复发积分
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。

- `TC-017` 游戏广告加成奖励与基础奖励一致性
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。

- `TC-018` 多广告 ID 轮换与限次生效
  - 通过 `verify_game_ad_flow.py --execute` 覆盖。

- `TC-021` 不满足门槛时不能提现
  - 通过 `verify_points_withdrawal_flow.py --execute` 覆盖首提门槛不足与可提现积分不足两种拦截。

- `TC-022` 满足门槛时提现申请成功并冻结积分
  - 通过 `verify_points_withdrawal_flow.py --execute` 覆盖。

- `TC-023` 提现驳回后积分退回
  - 通过 `verify_points_withdrawal_flow.py --execute` 覆盖。

- `TC-025` 会员开通后权益即时生效
  - 通过 `verify_vip_entitlements.py --execute` 覆盖。

- `TC-035` 会员支付成功回调不能重复开权益/返利
  - 通过更新后的 `verify_vip_entitlements.py --execute` 覆盖“同一订单支付回调重复执行一次”。
  - 已确认 `vip_gift` 流水只生成 1 条。

### 5.2 线上健康与广告配置验证通过

- `GET /health` 返回 `200`
- `GET /game/tasks/status` 未登录返回 `401`
- `GET /admin/ad/game-bonus-config` 返回 `200`
- 已确认线上存在 3 个真实 `game_bonus` 广告位：
  - `adunit-e66ca7039925b740`
  - `adunit-7c61b0922792ddc9`
  - `adunit-a921c4e0383a451f`

### 5.3 前端证据链已补清

- 已明确前端工程不在 `myproject` 内，而在 [video-ts/package.json](d:/Desktop/vedo-project/video-ts/package.json)
- `build:mp-weixin` 在真实前端目录下执行通过

## 6. 未覆盖测试项

以下项本轮仍未形成足够的可复核执行证据，不能判定为已通过：

- `TC-004` token 鉴权不信任前端 `user_id`
- `TC-011` 签到广告加成仅发放一次
- `TC-015` 普通用户超过每日 10 次后不可继续得分
- `TC-016` 不同会员等级任务次数上限正确
- `TC-019` 我的页面统一积分资产展示正确
- `TC-020` 每次积分变化都有对应流水
- `TC-026` 一级返利/二级分销冻结入账正确
- `TC-027` 用户只能绑定一次上级
  - 服务层“重复绑定不改写”已覆盖，但缺少真实接口联调与页面链路证据。
- `TC-029` 免费用户复制资源前需完成互动/广告
- `TC-032` 前台不得出现高收益承诺文案
- `TC-034` 账户汇总、流水、页面展示三方一致
- `TC-036` 退款后奖励处理正确

## 7. 发现的问题

### 7.1 已修复

- `verify_vip_entitlements.py` 在 Python 3.10 环境下无法执行。
  - 已修复。

- 默认提现配置下普通用户后续提现门槛错误。
  - 已补 `withdraw_min_first / normal / member` 默认值。

### 7.2 当前仍存在的问题

- 前端 `type-check` 仍失败。
  - 真实命令：`npm.cmd run type-check`
  - 错误位置：`vue-tsc@1.8.27 + TypeScript 5.9.3 + Node.js v22.18.0`
  - 报错摘要：`Search string not found: "/supportedTSExtensions = .*(?=;)/"`
  - 当前判断：这是工具链兼容问题，不是本轮已验证业务链路的直接失败。

## 8. 建议修复项

- 优先补 `签到广告加成` 专项脚本或接口验证链路。
  - 当前 `checkin_records` 已有 `ad_bonus_used`、`ad_event_id` 字段，但本轮没有完整执行证据。

- 补 `邀请返利 / 二级分销 / 冻结积分 / 解冻` 专项验证。
  - 当前是最关键的剩余 P0 风险之一。

- 补 `退款逆向处理` 专项验证。

- 补 `账户汇总 + 积分流水 + 页面展示` 三方对账验证。

- 固定前端类型检查工具链版本。
  - 建议锁一套可执行的 `Node LTS + vue-tsc + TypeScript` 组合，再跑正式 QA。

## 9. 需要人工确认部分

- 真机微信静默登录与邀请码链路。
- 我的页面资产展示、积分明细展示、提现弹窗交互。
- 影视资源复制权限与会员权益差异。
- 前台文案合规巡检。
- 退款、邀请返利冻结与解冻、页面对账联调。

## 10. 是否涉及高风险模块

涉及。

本轮已触达的高风险模块：
- 登录建档与邀请绑定
- 签到
- 小游戏结算
- 广告幂等与轮换
- 会员权益
- 积分提现

本轮仍未完全覆盖的高风险模块：
- 签到广告加成
- 邀请返利 / 二级分销 / 冻结积分
- 退款逆向
- 页面账务一致性
- 影视权益控制

## 11. 测试结果结论

这轮相对上一版，自测证据链已经明显补强：

- 原先只能证明“小游戏 / 广告 / 会员部分链路”，现在已经补到：
  - 登录/邀请
  - 签到
  - 积分提现
  - 支付回调幂等
- 原先“当前验收环境无法执行”的核心问题，已经通过生产运行容器的回滚式脚本验证补成了真实可复核结果。
- 前端真实工程路径和构建命令也已经明确。

但当前仍不能宣称“全部通过”，原因是仍有一批未覆盖的 P0 项，尤其是：
- 签到广告加成
- 邀请返利 / 二级分销 / 冻结积分
- 退款逆向
- 账务三方一致性

因此本轮结论是：

**已显著缩小验收缺口，但暂不建议直接判定为全部通过，建议交给 AI 测试官基于本报告继续复测。**
