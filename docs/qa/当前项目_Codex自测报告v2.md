# 当前项目_Codex自测报告 v2

## 1. 本次自测目标

根据 `当前项目_验收报告v1.md` 的“不通过”结论，本轮作为开发 Codex 只围绕验收报告中列出的 4 张 Bug 单做最小修复与补证：

1. P0：签到广告加成链路缺少可复核幂等验证证据。
2. P0：邀请返利 / 二级分销 / 冻结积分链路缺少专项验收闭环。
3. P0：账务三方一致性与“我的页”资产展示缺少正式验收证据。
4. P1：前端 `type-check` 工具链失败，回归防线未闭合。

本轮未扩展到验收报告之外的大范围业务重构，也未处理未出现在 Bug 单中的页面体验优化。

## 2. 修改文件

### 后端 `myproject`

| 文件 | 说明 |
|---|---|
| `controllers/checkin.py` | 新增 `POST /checkin/ad-bonus`，用于领取每日签到广告加成 |
| `schemas/checkin.py` | 新增 `CheckinAdBonusRequest` |
| `services/checkin_service.py` | 新增签到广告加成领取逻辑，校验已签到、广告完成、同日幂等 |
| `services/payment_service.py` | 会员支付返利从旧现金余额改为阶段二冻结积分流水，默认一级 50%、二级 5%，补重复发放拦截 |
| `services/commission_service.py` | 新增佣金冻结积分解冻方法 |
| `services/points_account_service.py` | 新增 `release_frozen_points`，支持冻结积分转可提现积分 |
| `services/config_service.py` | 更新默认返利配置为一级 50%、二级 5%，提现默认门槛沿用阶段二配置 |
| `services/mine_assets_service.py` | “我的页”资产聚合补充 `locked_withdraw_points`、`withdrawn_points` |
| `schemas/mine.py` | “我的页”资产响应 schema 补充锁定提现积分和已提现积分字段 |
| `scripts/verify_checkin_ad_bonus_flow.py` | 新增签到广告加成专项验证脚本 |
| `scripts/verify_invite_rebate_flow.py` | 新增邀请返利、冻结积分、解冻幂等专项验证脚本 |
| `scripts/verify_points_asset_consistency.py` | 新增账户、流水、“我的页”资产三方一致性验证脚本 |

### 前端 `video-ts`

| 文件 | 说明 |
|---|---|
| `package.json` | 升级 `vue-tsc` 与 `@vue/tsconfig`，修复 TS 5.9 下工具链崩溃 |
| `pnpm-lock.yaml` | 同步锁定前端类型检查依赖 |
| `tsconfig.json` | 纳入根目录声明文件，排除未引用且扩展名错误的遗留 `test.ts` |
| `shims-uni.d.ts` | 增加全局 `wx` 声明 |
| `src/types/index.d.ts` | 补充旧 `_id` 兼容字段，修正视频解析响应类型 |
| `src/store/anime.ts` | 媒体权限 rule 写入前做类型窄化，`description` 改为可选 |
| `src/pages/mine/compent/chat.vue` | 补充分页加载时的用户空值保护 |

说明：前端仓库在本轮开始前已有大量历史脏改动，本报告只记录与本轮 Bug 单直接相关的修改与验证。

## 3. 核心实现说明

### 3.1 Bug 单 1：签到广告加成幂等

已新增 `POST /checkin/ad-bonus`，请求参数为 `ad_event_id`。

服务层规则：

1. 用户当天必须已完成基础签到。
2. `ad_event_id` 必须存在对应用户的 `complete` 广告事件。
3. 同一用户同一天只允许领取一次签到广告加成。
4. 重放同一个 `ad_event_id` 或换一个新的同日广告事件再次领取，均不重复发积分。
5. 成功后同步更新 `checkin_records`、`daily_task_stats`、`points_ledger` 和 `user_accounts`。

新增脚本：`scripts/verify_checkin_ad_bonus_flow.py`

覆盖点：基础签到、首次广告加成、同一 `ad_event_id` 重放、同日第二个广告事件重复领取、账户/流水/日统计一致性。

### 3.2 Bug 单 2：邀请返利、二级分销、冻结积分

已将会员支付后的邀请返利改为阶段二积分账务：

1. 默认一级返利：订单金额 * 50% * 兑换比例。
2. 默认二级返利：订单金额 * 5% * 兑换比例。
3. 返利默认进入 `user_accounts.frozen_points`。
4. 写入 `points_ledger`，`source=invite`，`change_type=invite_rebate_frozen`。
5. 通过 `related_type=commission_record`、`related_id=commission_record.id` 关联旧佣金记录。
6. 重复支付回调不会重复创建佣金记录或重复发放积分。
7. 新增冻结积分解冻能力，解冻后 `frozen_points` 减少、`withdrawable_points` 增加，并写 `invite_rebate_unfreeze` 流水。

新增脚本：`scripts/verify_invite_rebate_flow.py`

覆盖点：一级 50%、二级 5%、冻结积分入账、重复支付回调幂等、解冻幂等。

### 3.3 Bug 单 3：账务三方一致性与资产展示

已补充“我的页”资产响应字段：

1. `locked_withdraw_points`
2. `withdrawn_points`

新增脚本：`scripts/verify_points_asset_consistency.py`

覆盖点：

1. 签到积分到账。
2. 游戏积分到账。
3. 邀请返利冻结积分到账。
4. 提现锁定与驳回退回。
5. `user_accounts` 与 `points_ledger` 最新余额一致。
6. `MineAssetsService.get_assets()` 返回的 `points_wallet` 与账户表一致。
7. `PointsLedgerService.list_user_ledger()` 返回的账户摘要与账户表一致。

### 3.4 Bug 单 4：前端 type-check 工具链

处理结果：

1. `vue-tsc` 从 `1.8.27` 升级到 `3.3.3`。
2. `@vue/tsconfig` 从 `0.1.3` 升级到 `0.9.1`。
3. 排除未引用的遗留文件 `src/pages/mine/compent/test.ts`，该文件内容是 Vue SFC，但扩展名是 `.ts`。
4. 补全 `wx` 全局声明和若干兼容类型。

结果：`npm.cmd run type-check` 已通过。

## 4. 已执行测试

### 4.1 后端静态检查

命令：

```powershell
python -m py_compile services\checkin_service.py services\payment_service.py services\points_account_service.py services\commission_service.py services\mine_assets_service.py schemas\checkin.py schemas\mine.py controllers\checkin.py scripts\verify_checkin_ad_bonus_flow.py scripts\verify_invite_rebate_flow.py scripts\verify_points_asset_consistency.py scripts\verify_checkin_flow.py scripts\verify_login_invite_flow.py scripts\verify_points_withdrawal_flow.py scripts\verify_vip_entitlements.py scripts\verify_game_ad_flow.py
```

结果：通过。

### 4.2 后端专项脚本 dry-run

| 脚本 | 结果 | 覆盖点 |
|---|---|---|
| `python scripts\verify_login_invite_flow.py` | 通过 | 登录建档、邀请绑定、不改绑、不自邀、token openid |
| `python scripts\verify_checkin_flow.py` | 通过 | 基础签到、重复签到、会员签到、流水/日统计 |
| `python scripts\verify_checkin_ad_bonus_flow.py` | 通过 | 签到广告加成、同日幂等、广告事件重放 |
| `python scripts\verify_points_withdrawal_flow.py` | 通过 | 提现门槛、不足拦截、锁定、驳回退回、成功结转 |
| `python scripts\verify_invite_rebate_flow.py` | 通过 | 一级/二级返利、冻结积分、重复回调、解冻 |
| `python scripts\verify_points_asset_consistency.py` | 通过 | 账户、流水、“我的页”资产三方一致性 |
| `python scripts\verify_game_ad_flow.py` | 通过 | 游戏广告轮换、限频、`ad_event_id` 幂等、`round_id` 幂等 |
| `python scripts\verify_vip_entitlements.py` | 通过 | 会员赠分、任务次数、提现会员门槛、支付回调幂等 |

### 4.3 后端专项脚本 `--execute`

本地执行以下命令时被环境阻塞：

```powershell
python scripts\verify_checkin_ad_bonus_flow.py --execute
python scripts\verify_invite_rebate_flow.py --execute
python scripts\verify_points_asset_consistency.py --execute
python scripts\verify_checkin_flow.py --execute
python scripts\verify_points_withdrawal_flow.py --execute
```

阻塞原因：当前本地数据库缺少阶段二表，包括但不限于：

1. `user_accounts`
2. `points_ledger`
3. `checkin_records`
4. `daily_task_stats`
5. `game_rounds`
6. `ad_event_records`

结论：本轮已完成脚本与代码层验证，但执行型数据验证需要在已执行阶段二 Alembic 迁移的联调库/生产镜像环境复跑。

### 4.4 前端验证

命令：

```powershell
npm.cmd run type-check
npm.cmd run build:mp-weixin
```

结果：

1. `type-check`：通过。
2. `build:mp-weixin`：通过。

构建输出仍有 Sass legacy API warning 和 uni-app 新版本提示，不影响本轮通过结论。

## 5. 已通过测试项

本轮新增或补强通过的项目：

| 编号 | 测试项 | 当前结论 | 证据 |
|---|---|---|---|
| TC-011 | 签到广告加成仅发放一次 | 代码层与 dry-run 通过，待迁移库 `--execute` | `verify_checkin_ad_bonus_flow.py` |
| TC-020 | 每次积分变化有对应流水 | 代码层与 dry-run 补强，待迁移库 `--execute` | `verify_points_asset_consistency.py` |
| TC-026 | 一级返利 / 二级分销冻结入账正确 | 代码层与 dry-run 通过，待迁移库 `--execute` | `verify_invite_rebate_flow.py` |
| TC-034 | 账户汇总、流水、页面展示三方一致 | 代码层与 dry-run 补强，待迁移库 `--execute` | `verify_points_asset_consistency.py` |
| Bug 单 4 | 前端 type-check 工具链 | 通过 | `npm.cmd run type-check` |
| 回归 | 小程序构建 | 通过 | `npm.cmd run build:mp-weixin` |

继续保持通过或 dry-run 可复核的项目：

1. TC-001 至 TC-003：登录建档、邀请绑定、自邀拦截。
2. TC-007 至 TC-009：基础签到、重复签到、会员签到。
3. TC-013 至 TC-018：小游戏结算、广告加倍、多广告位轮换与幂等。
4. TC-021 至 TC-023：积分提现门槛、锁定、驳回退回、成功结转。
5. TC-025、TC-035：会员权益生效、重复支付回调不重复赠分。

## 6. 未覆盖测试项

以下内容本轮仍未形成完整通过结论：

| 编号 | 未覆盖项 | 原因 |
|---|---|---|
| TC-004 | token 鉴权不信任前端 `user_id` 的接口级越权验证 | 本轮未新增接口级自动化用例，只保留已有登录脚本覆盖 token openid 基础逻辑 |
| TC-005、TC-012、TC-019 | 首页 / 任务中心 / 我的页真机展示 | 本轮未做微信开发者工具真机页面截图验收 |
| TC-015、TC-016 | 普通用户 10 次、会员 100/150/200 次边界执行 | 现有游戏脚本覆盖广告幂等，未完整跑到次数上限边界 |
| TC-029、TC-030 | 影视资源复制权限与会员差异 | 本轮 Bug 单未要求修复影视权益链路 |
| TC-032 | 前台高风险收益文案巡检 | 本轮未做页面文案人工巡检 |
| TC-033 | 关键埋点完整性 | 本轮未补埋点专项脚本 |
| TC-036 | 退款后奖励处理正确 | 本轮未发现对应退款 Bug 单，未扩展实现 |

## 7. 发现的问题

1. 本地数据库未执行阶段二迁移，导致所有依赖 `user_accounts`、`points_ledger` 的 `--execute` 脚本无法在本地真实落库验证。
2. 前端 `type-check` 原先不是业务类型错误，而是工具链崩溃；升级工具链后暴露并修复了真实类型声明问题。
3. 前端仓库存在较多历史脏改动和删除状态文件，本轮未回滚这些历史内容。
4. `src/pages/mine/compent/test.ts` 是未引用的遗留文件，内容为 Vue SFC，但扩展名为 `.ts`；本轮仅在 `tsconfig.json` 中排除，未删除文件。
5. 签到广告加成后端接口已补齐，但前端是否已有明确入口仍需真机确认。

## 8. 已修复的问题

1. 修复签到广告加成无法形成幂等闭环的问题。
2. 修复会员支付邀请返利仍走旧现金余额、默认一级比例不符合阶段二要求的问题。
3. 补齐冻结积分解冻能力，形成返利冻结与解冻验证闭环。
4. 补齐“我的页”资产中锁定提现积分和已提现积分展示字段。
5. 修复前端 `type-check` 工具链崩溃，并让 `type-check` 通过。

## 9. 建议修复项

1. 在已执行阶段二 Alembic 迁移的联调库或当前生产镜像环境复跑：

```powershell
python scripts\verify_checkin_ad_bonus_flow.py --execute
python scripts\verify_invite_rebate_flow.py --execute
python scripts\verify_points_asset_consistency.py --execute
```

2. 若测试清单要求前端签到广告加成入口，下一步应接入前端按钮和激励广告调用，再做真机测试。
3. 补充普通用户与会员游戏次数上限边界脚本，覆盖 10 / 100 / 150 / 200 次。
4. 单独生成影视资源权益、退款回滚、埋点完整性的 Bug 单或测试任务，不建议混在本轮 Bug 修复里。
5. 对前端页面做一次高风险收益文案人工巡检。

## 10. 需要人工确认部分

1. 阶段二邀请返利默认“冻结积分”是否完全替代旧现金佣金余额展示。
2. 冻结积分解冻的实际运营规则：按天自动解冻、后台手动解冻，还是支付无退款期后定时任务解冻。
3. 签到广告加成是否需要前端明确入口，或仅作为后端能力预留。
4. `src/pages/mine/compent/test.ts` 是否可以后续单独删除或改名为 `.vue` 归档。
5. 本轮新增后端接口是否需要同步生成前端 API 封装。

## 11. 当前自测结论

**结论：需要 AI 测试官复核。**

本轮已按 v1 验收报告中的 4 张 Bug 单完成最小修复与补证：

1. P0 的签到广告加成、邀请返利冻结、账务一致性均已补代码和专项脚本。
2. P1 的前端 `type-check` 已修复并通过。
3. 小程序构建仍通过。

但由于当前本地数据库缺少阶段二迁移表，P0 的 `--execute` 执行型验证还需要在迁移后的联调库或生产镜像环境复跑。因此本报告不建议直接进入最终人工上线确认，建议先交由 AI 测试官基于 v2 报告做下一轮复测与回归判断。
